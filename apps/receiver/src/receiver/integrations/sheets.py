"""Google Sheets append-row notifier — one row per booking event.

env:
- GOOGLE_SHEETS_CREDENTIALS_JSON   service-account JSON (the entire blob,
                                    one line; private_key field uses literal
                                    `\\n` escapes — that's fine, json.loads
                                    handles it)
- GOOGLE_SHEETS_SPREADSHEET_ID     the sheet id from the URL
- GOOGLE_SHEETS_TAB_NAME           optional, defaults to "Bookings"

Skips cleanly when credentials/spreadsheet are not set.

Implementation notes — kept to two small deps:
- We avoid `google-auth` + `requests` (heavyweight + sync transport).
- Instead we sign a service-account JWT with PyJWT (RS256) and exchange
  it for an access token at the standard OAuth2 token endpoint, then
  call the Sheets values-append endpoint via httpx. ~30 lines of glue.
"""
from __future__ import annotations

import json
import logging
import os
import time

import httpx
import jwt

from receiver.extract import ExtractedBooking

log = logging.getLogger(__name__)

ENV_CREDS = "GOOGLE_SHEETS_CREDENTIALS_JSON"
ENV_SPREADSHEET = "GOOGLE_SHEETS_SPREADSHEET_ID"
ENV_TAB = "GOOGLE_SHEETS_TAB_NAME"

_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Column order — keep aligned with the receiver's `bookings` table so the
# sheet reads as a plain mirror of the Postgres ledger.
_HEADER = [
    "received_at_iso",
    "event_type",
    "cal_booking_uid",
    "client_slug",
    "prospect_name",
    "prospect_email",
    "prospect_company",
    "scheduled_at_iso",
    "timezone",
    "video_link",
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_content",
    "utm_term",
]


def is_configured() -> bool:
    return bool(os.environ.get(ENV_CREDS) and os.environ.get(ENV_SPREADSHEET))


def _row_for_booking(b: ExtractedBooking) -> list[str]:
    utm = b.utm or {}
    return [
        time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        b.event_type,
        b.cal_booking_uid,
        b.client_slug or "",
        b.prospect_name or "",
        b.prospect_email or "",
        b.prospect_company or "",
        b.scheduled_at.isoformat() if b.scheduled_at else "",
        b.timezone or "",
        b.video_link or "",
        utm.get("utm_source") or "",
        utm.get("utm_medium") or "",
        utm.get("utm_campaign") or "",
        utm.get("utm_content") or "",
        utm.get("utm_term") or "",
    ]


async def _access_token(creds: dict, client: httpx.AsyncClient) -> str | None:
    now = int(time.time())
    assertion = jwt.encode(
        {
            "iss": creds["client_email"],
            "scope": " ".join(_SCOPES),
            "aud": _TOKEN_ENDPOINT,
            "iat": now,
            "exp": now + 3600,
        },
        creds["private_key"],
        algorithm="RS256",
    )
    try:
        resp = await client.post(
            _TOKEN_ENDPOINT,
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": assertion,
            },
            timeout=10.0,
        )
    except httpx.HTTPError as exc:
        log.warning("sheets: token-exchange network error: %s", exc)
        return None
    if resp.status_code >= 400:
        log.warning("sheets: token-exchange failed (HTTP %s): %s", resp.status_code, resp.text[:300])
        return None
    return resp.json().get("access_token")


async def dispatch(booking: ExtractedBooking, raw_payload: dict, *, pool=None) -> None:
    creds_raw = os.environ.get(ENV_CREDS)
    spreadsheet = os.environ.get(ENV_SPREADSHEET)
    tab = os.environ.get(ENV_TAB) or "Bookings"
    if not (creds_raw and spreadsheet):
        log.info("sheets: skipped — not configured (need %s + %s)", ENV_CREDS, ENV_SPREADSHEET)
        return

    try:
        creds = json.loads(creds_raw)
    except json.JSONDecodeError as exc:
        log.warning("sheets: %s is not valid JSON: %s", ENV_CREDS, exc)
        return
    if "client_email" not in creds or "private_key" not in creds:
        log.warning(
            "sheets: %s missing required service-account keys (client_email, private_key)",
            ENV_CREDS,
        )
        return

    async with httpx.AsyncClient(timeout=15.0) as client:
        token = await _access_token(creds, client)
        if not token:
            return

        # values:append with USER_ENTERED treats quoted text as text and
        # parses dates/numbers like a human typing into the cell would.
        url = (
            f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet}"
            f"/values/{tab}!A:Z:append"
            f"?valueInputOption=USER_ENTERED&insertDataOption=INSERT_ROWS"
        )
        try:
            resp = await client.post(
                url,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={"values": [_row_for_booking(booking)]},
            )
        except httpx.HTTPError as exc:
            log.warning("sheets: append network error for booking %s: %s", booking.cal_booking_uid, exc)
            return

    if resp.status_code >= 400:
        log.warning(
            "sheets: append rejected for booking %s (HTTP %s): %s",
            booking.cal_booking_uid, resp.status_code, resp.text[:300],
        )
        return
    log.info("sheets: appended row for booking %s (tab=%s)", booking.cal_booking_uid, tab)
