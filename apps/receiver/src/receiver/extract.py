"""Extract the columns we care about from a cal.diy webhook envelope.

The envelope shape is:

    {
      "triggerEvent": "BOOKING_CREATED",
      "createdAt":    "2026-...",
      "payload":      { ...booking fields..., "tracking": { utm_* } }
    }

We never *trust* this extraction to be complete — `raw_payload_json` is
also stored on every row, so anything we miss can be backfilled later.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


_UTM_KEYS = ("utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term")


@dataclass
class ExtractedBooking:
    cal_booking_uid: str
    event_type: str
    client_slug: str | None
    prospect_name: str | None
    prospect_email: str | None
    prospect_company: str | None
    scheduled_at: datetime | None
    timezone: str | None
    video_link: str | None
    utm: dict[str, str | None]
    custom_responses: dict[str, Any]


def _str(node: Any) -> str | None:
    if node is None:
        return None
    if isinstance(node, (str, int, float, bool)):
        return str(node)
    return None


def _response_value(payload: dict, key: str) -> str | None:
    """cal.diy stores booking-question answers as `{key: {value: ...}}`,
    sometimes flattened to `{key: <value>}` depending on the field type."""
    responses = payload.get("responses") or {}
    if not isinstance(responses, dict):
        return None
    raw = responses.get(key)
    if raw is None:
        return None
    if isinstance(raw, dict):
        return _str(raw.get("value"))
    return _str(raw)


def _video_link(payload: dict) -> str | None:
    """cal.diy puts the meeting URL in different places depending on integration.
    Probe the common ones."""
    metadata = payload.get("metadata") or {}
    if isinstance(metadata, dict):
        for k in ("videoCallUrl", "hangoutLink"):
            if metadata.get(k):
                return _str(metadata[k])
    vcd = payload.get("videoCallData") or {}
    if isinstance(vcd, dict) and vcd.get("url"):
        return _str(vcd["url"])
    loc = payload.get("location")
    if isinstance(loc, str) and loc.startswith("http"):
        return loc
    return None


def _scheduled_at(payload: dict) -> datetime | None:
    raw = payload.get("startTime")
    if not raw:
        return None
    try:
        # cal.diy emits ISO-8601 with a `Z` suffix.
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None


def _utm(payload: dict) -> dict[str, str | None]:
    """Pull UTM values out of the webhook payload.

    cal.diy in this build has TWO UTM-shaped surfaces, only one of which
    actually rides the webhook envelope:

      1. `payload.metadata.utm_*` — populated when the booker URL carries
         `?metadata[utm_source]=…&metadata[utm_campaign]=…` etc. The
         booker UI (apps/web/modules/bookings/components/BookerWebWrapper.tsx)
         lifts those query params straight into the booking's `metadata`,
         which IS round-tripped through to webhook payloads. **This is the
         path our marketing/embed links must use.**

      2. `payload.tracking.{utm_*}` — populated when the booking POST body
         includes a `tracking` field. cal.diy stores it in its own
         `Tracking` table but does NOT include it in webhook payloads in
         this build. Kept here as a fallback in case a future cal.diy
         release fixes that gap.
    """
    metadata = payload.get("metadata") or {}
    tracking = payload.get("tracking") or {}
    out: dict[str, str | None] = {}
    for key in _UTM_KEYS:
        v = None
        if isinstance(metadata, dict):
            v = _str(metadata.get(key))
        if v is None and isinstance(tracking, dict):
            v = _str(tracking.get(key))
        out[key] = v
    return out


def extract(envelope: dict) -> ExtractedBooking:
    event_type = _str(envelope.get("triggerEvent")) or "UNKNOWN"
    payload = envelope.get("payload") or {}
    if not isinstance(payload, dict):
        payload = {}

    organizer = payload.get("organizer") or {}
    organizer = organizer if isinstance(organizer, dict) else {}

    attendees = payload.get("attendees") or []
    first_attendee = attendees[0] if isinstance(attendees, list) and attendees else {}
    first_attendee = first_attendee if isinstance(first_attendee, dict) else {}

    return ExtractedBooking(
        cal_booking_uid=_str(payload.get("uid")) or _str(payload.get("bookingId")) or "",
        event_type=event_type,
        client_slug=_str(organizer.get("username")),
        prospect_name=_str(first_attendee.get("name")),
        prospect_email=_str(first_attendee.get("email")),
        prospect_company=_response_value(payload, "company"),
        scheduled_at=_scheduled_at(payload),
        timezone=_str(first_attendee.get("timeZone")) or _str(organizer.get("timeZone")),
        video_link=_video_link(payload),
        utm=_utm(payload),
        custom_responses=payload.get("responses") or {},
    )
