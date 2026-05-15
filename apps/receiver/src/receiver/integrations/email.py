"""Resend transactional-email notifier — sends one email per handled event.

env:
- RESEND_API_KEY        (required)
- RESEND_FROM_EMAIL     (required)  e.g. onboarding@resend.dev for local dev
- AGENCY_NOTIFY_EMAIL   (required)  recipient
"""
from __future__ import annotations

import logging
import os
from html import escape

import httpx

from receiver.extract import ExtractedBooking

log = logging.getLogger(__name__)

ENV_API_KEY = "RESEND_API_KEY"
ENV_FROM = "RESEND_FROM_EMAIL"
ENV_TO = "AGENCY_NOTIFY_EMAIL"

_BASE = "https://api.resend.com/emails"

_SUBJECT_PREFIX = {
    "BOOKING_CREATED": "[Booking] New",
    "BOOKING_RESCHEDULED": "[Booking] Rescheduled",
    "BOOKING_CANCELLED": "[Booking] Cancelled",
    "BOOKING_REJECTED": "[Booking] Rejected",
}


def is_configured() -> bool:
    return all(os.environ.get(k) for k in (ENV_API_KEY, ENV_FROM, ENV_TO))


def _subject(booking: ExtractedBooking) -> str:
    prefix = _SUBJECT_PREFIX.get(booking.event_type, "[Booking]")
    who = booking.prospect_name or booking.prospect_email or booking.cal_booking_uid
    where = f" — {booking.client_slug}" if booking.client_slug else ""
    return f"{prefix}: {who}{where}"


def _html(booking: ExtractedBooking) -> str:
    rows = [
        ("Event", booking.event_type),
        ("Client", booking.client_slug or "—"),
        ("Prospect", booking.prospect_name or "—"),
        ("Email", booking.prospect_email or "—"),
        ("Company", booking.prospect_company or "—"),
        (
            "Scheduled",
            (booking.scheduled_at.isoformat() if booking.scheduled_at else "—")
            + (f" ({booking.timezone})" if booking.timezone else ""),
        ),
        ("Meeting link", booking.video_link or "—"),
        ("UTM source", (booking.utm or {}).get("utm_source") or "—"),
        ("UTM medium", (booking.utm or {}).get("utm_medium") or "—"),
        ("UTM campaign", (booking.utm or {}).get("utm_campaign") or "—"),
        ("UTM content", (booking.utm or {}).get("utm_content") or "—"),
        ("UTM term", (booking.utm or {}).get("utm_term") or "—"),
        ("Booking UID", booking.cal_booking_uid),
    ]
    body = "".join(
        f"<tr><td style='padding:4px 12px;color:#666'>{escape(k)}</td>"
        f"<td style='padding:4px 12px'><code>{escape(str(v))}</code></td></tr>"
        for k, v in rows
    )
    return f"<table style='font-family:-apple-system,sans-serif;font-size:14px'>{body}</table>"


async def dispatch(booking: ExtractedBooking, raw_payload: dict, *, pool=None) -> None:
    api_key = os.environ.get(ENV_API_KEY)
    sender = os.environ.get(ENV_FROM)
    recipient = os.environ.get(ENV_TO)
    if not (api_key and sender and recipient):
        log.info("email: skipped — not configured (need %s, %s, %s)", ENV_API_KEY, ENV_FROM, ENV_TO)
        return

    payload = {
        "from": sender,
        "to": [recipient],
        "subject": _subject(booking),
        "html": _html(booking),
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=15.0, headers=headers) as client:
        try:
            resp = await client.post(_BASE, json=payload)
        except httpx.HTTPError as exc:
            log.warning("email: network error for booking %s: %s", booking.cal_booking_uid, exc)
            return

    if resp.status_code >= 400:
        log.warning(
            "email: rejected booking %s with HTTP %s: %s",
            booking.cal_booking_uid, resp.status_code, resp.text[:300],
        )
        return
    # Log the Resend message id so ops can trace to the dashboard / GET /emails/{id}.
    try:
        message_id = resp.json().get("id", "?")
    except ValueError:
        message_id = "?"
    log.info(
        "email: sent %s for booking %s (resend_id=%s)",
        booking.event_type, booking.cal_booking_uid, message_id,
    )
