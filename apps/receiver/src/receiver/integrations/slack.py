"""Slack incoming-webhook notifier.

env: SLACK_WEBHOOK_URL
"""
from __future__ import annotations

import logging
import os

import httpx

from receiver.extract import ExtractedBooking

log = logging.getLogger(__name__)

ENV_WEBHOOK = "SLACK_WEBHOOK_URL"

_TITLES = {
    "BOOKING_CREATED": ":calendar: New booking",
    "BOOKING_RESCHEDULED": ":arrows_counterclockwise: Booking rescheduled",
    "BOOKING_CANCELLED": ":x: Booking cancelled",
    "BOOKING_REJECTED": ":no_entry_sign: Booking rejected",
}


def is_configured() -> bool:
    return bool(os.environ.get(ENV_WEBHOOK))


def _format_text(b: ExtractedBooking) -> str:
    title = _TITLES.get(b.event_type, b.event_type)
    when = b.scheduled_at.isoformat() if b.scheduled_at else "(no time)"
    parts = [
        f"*{title}*",
        f"client: `{b.client_slug or '?'}`",
        f"prospect: {b.prospect_name or '?'}"
        + (f" — {b.prospect_company}" if b.prospect_company else ""),
        f"scheduled: {when}" + (f" ({b.timezone})" if b.timezone else ""),
    ]
    if b.video_link:
        parts.append(f"meeting: <{b.video_link}|join>")
    campaign = b.utm.get("utm_campaign") if b.utm else None
    if campaign:
        parts.append(f"campaign: `{campaign}`")
    return "\n".join(parts)


async def dispatch(booking: ExtractedBooking, raw_payload: dict, *, pool=None) -> None:
    url = os.environ.get(ENV_WEBHOOK)
    if not url:
        log.info("slack: skipped — not configured")
        return

    body = {"text": _format_text(booking)}
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(url, json=body)
        except httpx.HTTPError as exc:
            log.warning("slack: network error for booking %s: %s", booking.cal_booking_uid, exc)
            return

    if resp.status_code >= 400:
        log.warning(
            "slack: rejected booking %s with HTTP %s: %s",
            booking.cal_booking_uid, resp.status_code, resp.text[:200],
        )
        return
    log.info("slack: posted %s for booking %s", booking.event_type, booking.cal_booking_uid)
