"""Polling worker: claim due reminder rows, send via Resend, mark sent.

Lives in the receiver process as an asyncio task spawned during the
FastAPI lifespan. Stops cleanly when the app is cancelled.

Concurrency model:
- Multiple receiver machines may run this loop simultaneously (production
  has min_machines_running=1 but auto-scales to 2 for HA deploys).
- Per-row claim uses `FOR UPDATE SKIP LOCKED` so each row is sent by
  exactly one machine.
- Within a single machine, the loop is sequential — Resend's free tier
  isn't worth contending on, and we get clean log lines per send.

Failure handling:
- Resend transient (network, 5xx): increment attempts, revert to pending
  for next tick. Capped at MAX_ATTEMPTS retries.
- Resend rejection (4xx, e.g. invalid From): immediately mark failed —
  retrying won't help, and surfacing the error in admin-ui matters more.
- Worker crash mid-send: a row stuck in 'processing' for >5 min is
  reset to 'pending' at next poll-loop iteration. Doesn't lose the work.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone

import httpx
from psycopg_pool import ConnectionPool

from .config import is_enabled, tick_seconds
from .template import ReminderContext, html, subject

log = logging.getLogger(__name__)

_RESEND_URL = "https://api.resend.com/emails"
_BATCH_SIZE = 25            # rows claimed per tick — bounded so a backlog
                            # gets worked off in many small chunks, not one
                            # giant one (also keeps log volume readable)
_STUCK_THRESHOLD_S = 300    # rows stuck in 'processing' >5 min get reset
_MAX_ATTEMPTS = 3           # transient retries before giving up


def _now():
    return datetime.now(timezone.utc)


def _select_due_sql() -> str:
    """SQL that claims a batch of due rows atomically.

    `FOR UPDATE SKIP LOCKED` is the crucial bit. Without it, two workers
    polling at the same time would both pull the same row and we'd
    double-send the email. With it, the second worker simply moves on
    to the next non-locked row.

    Updating `status='processing'` inside the same transaction guarantees
    the row leaves the visible-pending set before any other connection
    can see it. The cursor is `SELECT ... RETURNING *` so the worker
    immediately has the data it needs to send, no second SELECT.
    """
    return """
        WITH claimed AS (
            SELECT id
              FROM reminder_jobs
             WHERE status = 'pending'
               AND fire_at <= NOW()
             ORDER BY fire_at
             LIMIT %s
             FOR UPDATE SKIP LOCKED
        )
        UPDATE reminder_jobs r
           SET status = 'processing',
               last_attempt_at = NOW(),
               attempts = r.attempts + 1
          FROM claimed
         WHERE r.id = claimed.id
        RETURNING
            r.id, r.cal_booking_uid, r.recipient_email, r.recipient_role,
            r.offset_minutes, r.fire_at, r.booking_scheduled_at, r.attempts;
    """


def _join_booking_sql() -> str:
    """Pull the booking columns we render in the email body.

    Separate query (not a JOIN in the claim) because the claim query is
    write-locked and we want the booking lookup to be a cheap read on a
    different index. The booking row is immutable per (uid, event_type)
    so there's no concern about racing a writer.
    """
    return """
        SELECT prospect_name, prospect_email, prospect_company,
               host_email, scheduled_at, timezone, video_link,
               raw_payload_json
          FROM bookings
         WHERE cal_booking_uid = %s
         ORDER BY id DESC
         LIMIT 1
    """


def _manage_url_from_payload(raw_payload, uid: str) -> str | None:
    """Mirror of reminders.scheduler — kept local so the worker doesn't
    depend on the scheduler's internals at send time."""
    if not isinstance(raw_payload, dict) or not uid:
        return None
    metadata = raw_payload.get("metadata")
    if not isinstance(metadata, dict):
        return None
    base = metadata.get("bookerUrl")
    if not base:
        return None
    return f"{str(base).rstrip('/')}/reschedule/{uid}"


def _host_name_from_payload(raw_payload) -> str | None:
    if not isinstance(raw_payload, dict):
        return None
    org = raw_payload.get("payload", {}) if "payload" in raw_payload else raw_payload
    org = (org or {}).get("organizer") if isinstance(org, dict) else None
    if not isinstance(org, dict):
        return None
    return org.get("name") or org.get("username")


async def _send_one(client: httpx.AsyncClient, *, api_key: str, sender: str,
                    ctx: ReminderContext) -> tuple[bool, str | None]:
    """POST one email. Returns (ok, error_message_if_failed)."""
    payload = {
        "from": sender,
        "to": [ctx.recipient_email],
        "subject": subject(ctx),
        "html": html(ctx),
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        resp = await client.post(_RESEND_URL, json=payload, headers=headers)
    except httpx.HTTPError as exc:
        return False, f"network error: {exc}"

    if resp.status_code < 300:
        return True, None
    # 4xx is permanent (bad From, blocked recipient, etc); 5xx is transient.
    # We surface the body so admin-ui can show *what* Resend rejected.
    body = resp.text[:300]
    return False, f"HTTP {resp.status_code}: {body}"


def _reset_stuck_processing(pool: ConnectionPool) -> int:
    """Recovery sweep: anything stuck in 'processing' for >threshold
    gets put back to 'pending' so the next tick picks it up."""
    sql = f"""
        UPDATE reminder_jobs
           SET status = 'pending'
         WHERE status = 'processing'
           AND last_attempt_at < NOW() - INTERVAL '{_STUCK_THRESHOLD_S} seconds'
    """
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                n = cur.rowcount
            conn.commit()
    except Exception as exc:  # noqa: BLE001
        log.warning("reminder worker: stuck-row recovery failed: %s", exc)
        return 0
    if n:
        log.info("reminder worker: reset %d stuck 'processing' row(s) to pending", n)
    return n


async def _tick(pool: ConnectionPool, http: httpx.AsyncClient,
                api_key: str, sender: str) -> int:
    """Run one polling iteration. Returns the number of rows we tried to send.

    Splitting the loop body out makes it easy to unit-test (no asyncio
    sleep, no stop event) and to reason about per-iteration behavior.
    """
    # 1) Claim a batch.
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(_select_due_sql(), (_BATCH_SIZE,))
                claimed = cur.fetchall()
            conn.commit()
    except Exception as exc:  # noqa: BLE001
        log.warning("reminder worker: claim batch failed: %s", exc)
        return 0

    if not claimed:
        return 0

    # 2) Send each. For each, fetch the latest booking row to render
    #    contents (the booking is immutable per (uid,event_type) so this
    #    is safe to read without locking).
    for row in claimed:
        (rid, uid, recipient_email, role, offset_min,
         fire_at, sched_at, attempts) = row
        try:
            with pool.connection() as conn, conn.cursor() as cur:
                cur.execute(_join_booking_sql(), (uid,))
                bk = cur.fetchone()
        except Exception as exc:  # noqa: BLE001
            # If we can't even read the booking, defer to next tick
            # (treat as transient).
            log.warning("reminder worker: booking lookup failed for %s: %s", uid, exc)
            _mark(pool, rid, status="pending", error=f"booking lookup: {exc}",
                  bump_attempts=False)
            continue

        if not bk:
            # Booking row vanished (manual DB cleanup?). Mark cancelled
            # so we don't keep retrying.
            _mark(pool, rid, status="cancelled", error="booking row missing")
            continue

        (pn, pe, pcompany, host_email, b_sched, tz, video, raw_payload) = bk

        now = _now()
        minutes_until = max(0, int((b_sched - now).total_seconds() // 60))
        ctx = ReminderContext(
            recipient_role=role,
            recipient_email=recipient_email,
            minutes_until=minutes_until,
            scheduled_at=b_sched,
            display_tz=tz,
            host_name=_host_name_from_payload(raw_payload),
            host_email=host_email,
            prospect_name=pn,
            prospect_email=pe,
            prospect_company=pcompany,
            video_link=video,
            booking_uid=uid,
            manage_url=_manage_url_from_payload(raw_payload, uid),
        )

        ok, err = await _send_one(http, api_key=api_key, sender=sender, ctx=ctx)
        if ok:
            _mark(pool, rid, status="sent", error=None)
            log.info(
                "reminder: sent uid=%s role=%s offset=%dmin to %s",
                uid, role, offset_min, recipient_email,
            )
            continue

        # Distinguish permanent vs transient. Transient = retryable.
        permanent = err and err.startswith("HTTP 4")
        if permanent or attempts >= _MAX_ATTEMPTS:
            _mark(pool, rid, status="failed", error=err)
            log.warning(
                "reminder: failed uid=%s role=%s attempts=%d — %s",
                uid, role, attempts, err,
            )
        else:
            # Revert to pending; next tick will retry.
            _mark(pool, rid, status="pending", error=err, bump_attempts=False)
            log.info(
                "reminder: transient failure uid=%s attempts=%d — %s",
                uid, attempts, err,
            )

    return len(claimed)


def _mark(pool: ConnectionPool, row_id: int, *, status: str, error: str | None,
          bump_attempts: bool = True) -> None:
    """Single helper for the post-send write. Centralizes the logic so
    error/sent_at columns stay consistent."""
    sent_at_expr = "NOW()" if status == "sent" else "NULL"
    sql = f"""
        UPDATE reminder_jobs
           SET status = %s,
               last_error = %s,
               sent_at = CASE WHEN %s = 'sent' THEN NOW() ELSE sent_at END
         WHERE id = %s
    """
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (status, error, status, row_id))
            conn.commit()
    except Exception as exc:  # noqa: BLE001
        log.warning("reminder worker: mark(%s) failed for row %d: %s", status, row_id, exc)


async def run_worker(pool: ConnectionPool, stop: asyncio.Event) -> None:
    """Long-running task. Cancel by setting `stop`.

    Stays up regardless of whether the feature is enabled — the cost of an
    idle loop is one DB poll per tick, which is negligible. Disabling the
    feature is done by zeroing the offset env var; existing rows still get
    drained if they happen to be due.
    """
    api_key = os.environ.get("RESEND_API_KEY")
    sender = os.environ.get("RESEND_FROM_EMAIL")
    if not (api_key and sender):
        log.info("reminder worker: not started — RESEND_API_KEY or RESEND_FROM_EMAIL unset")
        return

    log.info(
        "reminder worker: starting (enabled=%s, tick=%ds, batch=%d)",
        is_enabled(), tick_seconds(), _BATCH_SIZE,
    )

    async with httpx.AsyncClient(timeout=20.0) as http:
        # First pass: recover any stuck rows from a previous crash.
        _reset_stuck_processing(pool)

        while not stop.is_set():
            try:
                await _tick(pool, http, api_key, sender)
            except Exception as exc:  # noqa: BLE001
                # Top-level guard — never let the loop die. Sleep a beat
                # so a hot error doesn't burn CPU.
                log.exception("reminder worker: tick crashed: %s", exc)
                await asyncio.sleep(5)
                continue
            # Sleep with early-exit so stop() takes effect promptly.
            try:
                await asyncio.wait_for(stop.wait(), timeout=tick_seconds())
            except asyncio.TimeoutError:
                pass

            # Periodic stuck-row sweep (cheap; UPDATE on partial set).
            _reset_stuck_processing(pool)

    log.info("reminder worker: stopped")
