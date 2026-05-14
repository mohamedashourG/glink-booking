"""
=============================================================================
 ⚠️  CAL.DIY WEB INTERNALS — DO NOT USE THIS MODULE OUTSIDE PROVISIONING ⚠️
=============================================================================

Everything in this file talks to cal.diy's *web app*, not its public API v2.

We use it because cal.diy's API v2 in this build does not expose:
  - user creation (no /v2/users controller; OAuth-managed-users path is org-gated)
  - per-user API key bootstrap (the apiKeys tRPC router is never mounted)

Instead we use the same surface the cal.diy *browser UI* uses:
  - POST /api/auth/signup                        (web route handler)
  - GET  /api/auth/csrf                          (NextAuth)
  - POST /api/auth/callback/credentials          (NextAuth credentials login)
  - POST /api/trpc/availability/schedule.create  (mounted tRPC viewer router)
  - POST /api/trpc/availability/schedule.update  (   "      "      "        )
  - POST /api/trpc/eventTypesHeavy/create        (   "      "      "        )
  - POST /api/trpc/eventTypesHeavy/update        (   "      "      "        )

Things that will break us if cal.diy upstream changes them:
  - URL paths above (especially the tRPC mount layout)
  - signup payload shape (`{email, password, username, language}`)
  - NextAuth `next-auth.session-token` cookie name
  - tRPC + superjson serialization conventions
  - The `bookingFields` validation that requires a required `email` entry
  - The schedule shape `[][]` indexed by weekday, with `Date` start/end

If you find yourself wanting to call cal.diy from another package in this
monorepo, DO NOT import from here. Either go through API v2 (preferred for
anything stable) or extend this module and let me know it grew.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any

import httpx


class CalWebError(RuntimeError):
    """Any failure from talking to cal.diy's web layer.

    Carries the URL and response body so the CLI can surface which step
    failed for which client.
    """

    def __init__(self, message: str, *, url: str = "", status: int = 0, body: str = ""):
        super().__init__(message)
        self.url = url
        self.status = status
        self.body = body


# ----- superjson helpers (request side only) ---------------------------------
# tRPC uses superjson. For our payloads the only non-JSON-native value is
# `datetime`. We walk the input, replace each datetime with an ISO string in
# `json`, and emit a `meta.values["dotted.path"] = ["Date"]` sidecar.

def _superjson_encode(value: Any) -> dict:
    meta_values: dict[str, list[str]] = {}

    def walk(node: Any, path: str) -> Any:
        if isinstance(node, dt.datetime):
            iso = node.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + f"{node.microsecond // 1000:03d}Z"
            meta_values[path] = ["Date"]
            return iso
        if isinstance(node, dict):
            return {k: walk(v, f"{path}.{k}" if path else k) for k, v in node.items()}
        if isinstance(node, list):
            return [walk(v, f"{path}.{i}" if path else str(i)) for i, v in enumerate(node)]
        return node

    json_part = walk(value, "")
    out: dict[str, Any] = {"json": json_part}
    if meta_values:
        out["meta"] = {"values": meta_values}
    return out


# ----- low-level web client --------------------------------------------------

@dataclass
class CalWebSession:
    """An authenticated cal.diy web session for one user.

    Holds the httpx Client carrying the NextAuth session cookie.
    Use it via `with` so the client closes cleanly.
    """

    base: str
    client: httpx.Client
    user_email: str

    def __enter__(self) -> "CalWebSession":
        return self

    def __exit__(self, *exc: object) -> None:
        self.client.close()

    # --- tRPC ---
    def trpc_mutation(self, endpoint: str, procedure: str, input_value: Any) -> Any:
        """POST /api/trpc/<endpoint>/<procedure> with superjson body.

        Returns the deserialized `result.data.json` payload (we ignore
        `result.data.meta` because nothing we read needs Date round-trip).
        """
        url = f"{self.base}/api/trpc/{endpoint}/{procedure}"
        body = _superjson_encode(input_value)
        try:
            resp = self.client.post(url, json=body, timeout=30.0)
        except httpx.HTTPError as exc:
            raise CalWebError(f"network error calling {url}: {exc}", url=url) from exc

        text = resp.text
        if resp.status_code >= 400:
            raise CalWebError(
                f"tRPC {endpoint}.{procedure} failed: HTTP {resp.status_code} — {_extract_trpc_error(text)}",
                url=url,
                status=resp.status_code,
                body=text,
            )
        try:
            payload = resp.json()
        except ValueError as exc:
            raise CalWebError(
                f"tRPC {endpoint}.{procedure} returned non-JSON body",
                url=url,
                status=resp.status_code,
                body=text,
            ) from exc

        if "error" in payload:
            raise CalWebError(
                f"tRPC {endpoint}.{procedure} returned error: {_extract_trpc_error(text)}",
                url=url,
                status=resp.status_code,
                body=text,
            )
        return payload["result"]["data"]["json"]


def _extract_trpc_error(body: str) -> str:
    try:
        import json

        data = json.loads(body)
        if isinstance(data, dict) and "error" in data:
            return str(data["error"].get("json", {}).get("message", body[:300]))
    except ValueError:
        pass
    return body[:300]


# ----- signup + login --------------------------------------------------------

class SignupConflict(CalWebError):
    """Raised when /api/auth/signup returns 409 (email/username taken)."""


def signup(base: str, *, email: str, password: str, username: str, language: str = "en") -> None:
    """POST /api/auth/signup. Raises SignupConflict on 409, CalWebError on others."""
    url = f"{base}/api/auth/signup"
    payload = {"email": email, "password": password, "username": username, "language": language}
    try:
        with httpx.Client() as cli:
            resp = cli.post(url, json=payload, timeout=30.0)
    except httpx.HTTPError as exc:
        raise CalWebError(f"network error during signup: {exc}", url=url) from exc

    if resp.status_code == 201:
        return
    body = resp.text[:500]
    if resp.status_code == 409:
        raise SignupConflict(f"signup conflict for {email}: {body}", url=url, status=409, body=body)
    raise CalWebError(
        f"signup failed for {email}: HTTP {resp.status_code} — {body}",
        url=url,
        status=resp.status_code,
        body=body,
    )


def login(base: str, *, email: str, password: str) -> CalWebSession:
    """NextAuth credentials login — returns a session bound to a cookie jar."""
    cli = httpx.Client(follow_redirects=False)
    csrf_url = f"{base}/api/auth/csrf"
    try:
        csrf_resp = cli.get(csrf_url, timeout=15.0)
    except httpx.HTTPError as exc:
        cli.close()
        raise CalWebError(f"network error fetching CSRF: {exc}", url=csrf_url) from exc
    if csrf_resp.status_code != 200:
        body = csrf_resp.text[:300]
        cli.close()
        raise CalWebError(
            f"CSRF fetch failed: HTTP {csrf_resp.status_code} — {body}",
            url=csrf_url,
            status=csrf_resp.status_code,
            body=body,
        )
    try:
        csrf_token = csrf_resp.json()["csrfToken"]
    except (ValueError, KeyError) as exc:
        cli.close()
        raise CalWebError(f"CSRF response missing csrfToken: {csrf_resp.text[:300]}", url=csrf_url) from exc

    callback_url = f"{base}/api/auth/callback/credentials"
    form = {
        "csrfToken": csrf_token,
        "email": email,
        "password": password,
        "callbackUrl": f"{base}/",
        "json": "true",
    }
    try:
        login_resp = cli.post(callback_url, data=form, timeout=15.0)
    except httpx.HTTPError as exc:
        cli.close()
        raise CalWebError(f"network error during login: {exc}", url=callback_url) from exc
    if login_resp.status_code != 200:
        body = login_resp.text[:300]
        cli.close()
        raise CalWebError(
            f"login failed for {email}: HTTP {login_resp.status_code} — {body}",
            url=callback_url,
            status=login_resp.status_code,
            body=body,
        )
    if not any(c.name.endswith("session-token") for c in cli.cookies.jar):
        body = login_resp.text[:300]
        cli.close()
        raise CalWebError(
            f"login for {email} returned 200 but no session-token cookie was set; bad password?",
            url=callback_url,
            body=body,
        )

    return CalWebSession(base=base, client=cli, user_email=email)


# ----- typed convenience wrappers used by provisioning ----------------------

def _date_at(hour_minute: str) -> dt.datetime:
    """Build a 1970-01-01 UTC datetime that encodes only a time-of-day.

    cal.diy stores schedule start/end times as Date objects where only
    hours/minutes are meaningful (the date portion is conventionally
    1970-01-01). This matches the format the UI sends.
    """
    h, m = hour_minute.split(":")
    return dt.datetime(1970, 1, 1, int(h), int(m), 0, tzinfo=dt.timezone.utc)


def weekday_schedule(work_start: str, work_end: str) -> list[list[dict]]:
    """Mon–Fri working hours; weekends empty.

    Index 0 = Sunday … 6 = Saturday (matches cal.diy's getAvailabilityFromSchedule).
    """
    weekday = [{"start": _date_at(work_start), "end": _date_at(work_end)}]
    return [[], weekday, weekday, weekday, weekday, weekday, []]


def create_schedule(session: CalWebSession, *, name: str) -> tuple[int, int]:
    """Create an empty schedule, return `(scheduleId, userId)`.

    `userId` is the cal.diy user the session is authenticated as — it's only
    discoverable via response payloads like this one, so we capture it here
    rather than making a second round-trip later.
    """
    out = session.trpc_mutation("availability", "schedule.create", {"name": name})
    return int(out["schedule"]["id"]), int(out["schedule"]["userId"])


def update_schedule(
    session: CalWebSession,
    *,
    schedule_id: int,
    name: str,
    timezone: str,
    schedule: list[list[dict]],
) -> None:
    """Set timezone + per-weekday hours on an existing schedule."""
    session.trpc_mutation(
        "availability",
        "schedule.update",
        {
            "scheduleId": schedule_id,
            "timeZone": timezone,
            "name": name,
            "isDefault": True,
            "schedule": schedule,
        },
    )


def create_event_type(
    session: CalWebSession,
    *,
    title: str,
    slug: str,
    length_minutes: int,
) -> int:
    """Create a bare event type, return eventTypeId."""
    out = session.trpc_mutation(
        "eventTypesHeavy",
        "create",
        {
            "title": title,
            "slug": slug,
            "length": length_minutes,
            "hidden": False,
            "locations": [],
        },
    )
    return int(out["eventType"]["id"])


# ----- bookingFields shape ---------------------------------------------------
# cal.diy validates that the submitted `bookingFields` array contains an
# `email` entry with `required: true` (otherwise it throws
# `booking_fields_email_or_phone_required`). The system also pads in `name` +
# `email` on read if bookingFields is null, but on update we must include
# them ourselves.

_DEFAULT_SOURCE = [{"id": "default", "type": "default", "label": "Default"}]
_USER_SOURCE = [{"id": "user", "type": "user", "label": "User"}]


def standard_booking_fields(extra_questions: list[dict]) -> list[dict]:
    """Return [name, email, ...extra_questions] in cal.diy field-schema shape.

    `extra_questions` items are dicts like {"name": ..., "label": ...,
    "type": "text"|"textarea", "required": bool}.
    """
    fields: list[dict] = [
        {
            "name": "name",
            "type": "name",
            "required": True,
            "editable": "system",
            "sources": _DEFAULT_SOURCE,
        },
        {
            "name": "email",
            "type": "email",
            "required": True,
            "editable": "system-but-optional",
            "sources": _DEFAULT_SOURCE,
        },
    ]
    for q in extra_questions:
        fields.append(
            {
                "name": q["name"],
                "type": q.get("type", "text"),
                "label": q["label"],
                "required": bool(q.get("required", False)),
                "editable": "user",
                "sources": _USER_SOURCE,
            }
        )
    return fields


def update_event_type(
    session: CalWebSession,
    *,
    event_type_id: int,
    schedule_id: int,
    minimum_notice_minutes: int,
    before_buffer_minutes: int,
    after_buffer_minutes: int,
    rolling_window_days: int,
    booking_fields: list[dict],
) -> None:
    """Apply our standard booking-policy config to an existing event type."""
    session.trpc_mutation(
        "eventTypesHeavy",
        "update",
        {
            "id": event_type_id,
            "minimumBookingNotice": minimum_notice_minutes,
            "beforeEventBuffer": before_buffer_minutes,
            "afterEventBuffer": after_buffer_minutes,
            "periodType": "ROLLING",
            "periodDays": rolling_window_days,
            "periodCountCalendarDays": True,
            "scheduleId": schedule_id,
            "bookingFields": booking_fields,
        },
    )
