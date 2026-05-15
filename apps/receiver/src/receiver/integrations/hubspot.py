"""HubSpot CRM sync — contact upsert, meeting engagement, optional deal.

env:
- HUBSPOT_TOKEN              (required)  private-app access token
- HUBSPOT_PIPELINE_ID        (optional)  if set with HUBSPOT_DEAL_STAGE,
                                          a deal is upserted at that stage
- HUBSPOT_DEAL_STAGE         (optional)  pipeline-stage internal id

The deal step is best-effort *within* HubSpot too: if the pipeline /
stage isn't accepted, contact + meeting still sync and only the deal
step is skipped. We never let the deal step fail the whole integration.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from receiver.db import find_hubspot_meeting_id, set_hubspot_meeting_id
from receiver.extract import ExtractedBooking

log = logging.getLogger(__name__)

ENV_TOKEN = "HUBSPOT_TOKEN"
ENV_PIPELINE = "HUBSPOT_PIPELINE_ID"
ENV_DEAL_STAGE = "HUBSPOT_DEAL_STAGE"

_BASE = "https://api.hubapi.com"

# HubSpot's default association type IDs (V2 schema).
# 200 = contact↔meeting (primary), 4 = contact↔deal (primary).
_ASSOC_CONTACT_TO_MEETING = 200
_ASSOC_CONTACT_TO_DEAL = 4


def is_configured() -> bool:
    return bool(os.environ.get(ENV_TOKEN))


def _outcome_for_event(event_type: str) -> str | None:
    return {
        "BOOKING_CREATED": "SCHEDULED",
        "BOOKING_RESCHEDULED": "RESCHEDULED",
        "BOOKING_CANCELLED": "CANCELED",
        "BOOKING_REJECTED": "CANCELED",
    }.get(event_type)


def _ms(dt: datetime | None) -> int | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


async def _upsert_contact(client: httpx.AsyncClient, booking: ExtractedBooking) -> str | None:
    """Upsert by email; returns HubSpot contact id or None on failure."""
    if not booking.prospect_email:
        log.warning("hubspot: booking %s has no prospect email; skipping contact sync", booking.cal_booking_uid)
        return None

    name_parts = (booking.prospect_name or "").strip().split(maxsplit=1)
    properties: dict[str, Any] = {"email": booking.prospect_email}
    if name_parts:
        properties["firstname"] = name_parts[0]
        if len(name_parts) > 1:
            properties["lastname"] = name_parts[1]
    if booking.prospect_company:
        properties["company"] = booking.prospect_company
    for k, v in (booking.utm or {}).items():
        if v:
            properties[k] = v  # utm_source / utm_medium / utm_campaign / utm_content / utm_term

    # PATCH /crm/v3/objects/contacts/{email}?idProperty=email — upsert pattern.
    url = f"{_BASE}/crm/v3/objects/contacts/{booking.prospect_email}?idProperty=email"
    resp = await client.patch(url, json={"properties": properties})
    if resp.status_code == 404:
        # First-time contact — PATCH on a missing email returns 404. Create.
        resp = await client.post(f"{_BASE}/crm/v3/objects/contacts", json={"properties": properties})
    if resp.status_code >= 400:
        log.warning(
            "hubspot: contact upsert failed for %s (HTTP %s): %s",
            booking.prospect_email, resp.status_code, resp.text[:300],
        )
        return None
    return resp.json().get("id")


async def _create_or_update_meeting(
    client: httpx.AsyncClient,
    booking: ExtractedBooking,
    contact_id: str,
    existing_meeting_id: str | None,
) -> str | None:
    """Create a new meeting on first sight; update its time/outcome thereafter.

    Returns the meeting id, or None on failure.
    """
    outcome = _outcome_for_event(booking.event_type)
    start_ms = _ms(booking.scheduled_at)
    end_ms = _ms((booking.scheduled_at + timedelta(minutes=30)) if booking.scheduled_at else None)
    title = f"Booking: {booking.prospect_name or booking.prospect_email or 'attendee'}"
    body_lines = [
        f"cal_booking_uid: {booking.cal_booking_uid}",
        f"client: {booking.client_slug or '?'}",
        f"event_type: {booking.event_type}",
    ]
    if booking.video_link:
        body_lines.append(f"meeting link: {booking.video_link}")

    properties: dict[str, Any] = {
        # hs_timestamp is the engagement-activity time and is REQUIRED on
        # MEETING_EVENT objects. For a scheduled meeting it's the start time.
        "hs_timestamp": start_ms,
        "hs_meeting_title": title,
        "hs_meeting_body": "\n".join(body_lines),
        "hs_meeting_start_time": start_ms,
        "hs_meeting_end_time": end_ms,
    }
    if booking.video_link:
        properties["hs_meeting_external_url"] = booking.video_link
    if outcome:
        properties["hs_meeting_outcome"] = outcome
    # Drop nones — HubSpot rejects null on time fields.
    properties = {k: v for k, v in properties.items() if v is not None}

    if existing_meeting_id:
        url = f"{_BASE}/crm/v3/objects/meetings/{existing_meeting_id}"
        resp = await client.patch(url, json={"properties": properties})
        if resp.status_code >= 400:
            log.warning(
                "hubspot: meeting update failed for booking %s (HTTP %s): %s",
                booking.cal_booking_uid, resp.status_code, resp.text[:300],
            )
            return None
        return existing_meeting_id

    # Create + associate to the contact.
    create_url = f"{_BASE}/crm/v3/objects/meetings"
    body = {
        "properties": properties,
        "associations": [
            {
                "to": {"id": contact_id},
                "types": [
                    {
                        "associationCategory": "HUBSPOT_DEFINED",
                        "associationTypeId": _ASSOC_CONTACT_TO_MEETING,
                    }
                ],
            }
        ],
    }
    resp = await client.post(create_url, json=body)
    if resp.status_code >= 400:
        log.warning(
            "hubspot: meeting create failed for booking %s (HTTP %s): %s",
            booking.cal_booking_uid, resp.status_code, resp.text[:300],
        )
        return None
    return resp.json().get("id")


async def _maybe_upsert_deal(
    client: httpx.AsyncClient,
    booking: ExtractedBooking,
    contact_id: str,
) -> None:
    """Create-or-update a deal at the configured stage. Best-effort; logs and returns on any failure."""
    pipeline_id = os.environ.get(ENV_PIPELINE)
    deal_stage = os.environ.get(ENV_DEAL_STAGE)
    if not pipeline_id or not deal_stage:
        return  # not configured, silently skip — this is the documented behavior

    deal_name = f"glink: {booking.prospect_company or booking.prospect_email or booking.prospect_name or booking.cal_booking_uid}"
    properties = {
        "dealname": deal_name,
        "pipeline": pipeline_id,
        "dealstage": deal_stage,
    }
    body = {
        "properties": properties,
        "associations": [
            {
                "to": {"id": contact_id},
                "types": [
                    {
                        "associationCategory": "HUBSPOT_DEFINED",
                        "associationTypeId": _ASSOC_CONTACT_TO_DEAL,
                    }
                ],
            }
        ],
    }
    resp = await client.post(f"{_BASE}/crm/v3/objects/deals", json=body)
    if resp.status_code >= 400:
        # Don't fail the integration — the spec is explicit about this.
        log.warning(
            "hubspot: deal step skipped for booking %s (HTTP %s, pipeline=%s, stage=%s): %s",
            booking.cal_booking_uid, resp.status_code, pipeline_id, deal_stage, resp.text[:300],
        )
        return
    log.info("hubspot: deal created for booking %s", booking.cal_booking_uid)


async def dispatch(booking: ExtractedBooking, raw_payload: dict, *, pool=None) -> None:
    token = os.environ.get(ENV_TOKEN)
    if not token:
        log.info("hubspot: skipped — not configured")
        return

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=15.0, headers=headers) as client:
        contact_id = await _upsert_contact(client, booking)
        if not contact_id:
            return  # without a contact there's nothing to associate

        # Try the current uid first, then the previous uid (cal.diy mints a
        # new uid on reschedule and puts the original in payload.rescheduleUid).
        existing = None
        if pool is not None:
            existing = find_hubspot_meeting_id(pool, booking.cal_booking_uid)
            if existing is None and booking.previous_uid:
                existing = find_hubspot_meeting_id(pool, booking.previous_uid)
        meeting_id = await _create_or_update_meeting(client, booking, contact_id, existing)
        if meeting_id and pool is not None:
            set_hubspot_meeting_id(pool, booking.cal_booking_uid, booking.event_type, meeting_id)

        if booking.event_type == "BOOKING_CREATED":
            await _maybe_upsert_deal(client, booking, contact_id)

    log.info("hubspot: synced %s for booking %s", booking.event_type, booking.cal_booking_uid)
