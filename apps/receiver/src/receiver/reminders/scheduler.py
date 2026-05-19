"""Reminder lifecycle: insert / reschedule / cancel rows in `reminder_jobs`.

Called from the receiver's webhook handler **after** the booking row has
been inserted in `bookings`. Doing it post-insert means we never schedule
a reminder for a payload that fails durability — and rescheduling/
cancelling for an unknown uid is a safe no-op.

All writes are best-effort: any failure here is logged but does not bubble
back to the webhook handler. cal.diy already got its 2xx; we don't want a
reminder write hiccup to trigger a webhook retry.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from psycopg_pool import ConnectionPool

from receiver.extract import ExtractedBooking

from .config import (
    ReminderPolicy,
    policy_for_client,
    resolve_recipients,
)

log = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _manage_url_from_payload(raw_payload: dict, uid: str) -> str | None:
    """Best-effort 'reschedule/cancel here' link.

    cal.diy puts `metadata.bookerUrl` on the payload when it's set. The
    reschedule page is at `<bookerUrl>/reschedule/<uid>`. We don't have
    a perfect deep-link for cancel (cal.diy varies by version), so we
    point at reschedule — the cancel control is on the same page.

    Returns None when the payload doesn't carry the URL; the email then
    falls back to "Booking <uid>" footer without a link.
    """
    metadata = raw_payload.get("metadata") if isinstance(raw_payload, dict) else None
    base = (metadata or {}).get("bookerUrl") if isinstance(metadata, dict) else None
    if not base or not uid:
        return None
    return f"{str(base).rstrip('/')}/reschedule/{uid}"


def schedule_on_created(
    pool: ConnectionPool,
    booking: ExtractedBooking,
    raw_payload: dict,
) -> int:
    """Insert reminder rows for this newly-created booking.

    Returns the number of rows inserted (offsets × eligible recipients).
    Offsets whose `fire_at` is already in the past are skipped — there's
    no point queuing a "reminder" the operator will only see as immediate.
    """
    if booking.scheduled_at is None:
        log.info("reminder: skipped %s — no scheduled_at", booking.cal_booking_uid)
        return 0

    policy = policy_for_client(pool, booking.client_slug)
    if not policy.offsets_min or not policy.recipients:
        log.info(
            "reminder: skipped %s — policy empty (offsets=%s, recipients=%s)",
            booking.cal_booking_uid, policy.offsets_min, policy.recipients,
        )
        return 0

    recipients = resolve_recipients(
        policy,
        prospect_email=booking.prospect_email,
        host_email=booking.host_email,
    )
    if not recipients:
        log.info(
            "reminder: skipped %s — no recipient emails resolved (policy roles=%s)",
            booking.cal_booking_uid, policy.recipients,
        )
        return 0

    rows: list[tuple] = []
    now = _now()
    for offset in policy.offsets_min:
        fire_at = booking.scheduled_at - timedelta(minutes=offset)
        if fire_at <= now:
            # Past-the-window offsets are dropped silently. Common when
            # the operator books a slot 30 min from now with a 1-hour
            # reminder configured.
            continue
        for role, email in recipients:
            rows.append((
                booking.cal_booking_uid,
                booking.client_slug,
                booking.scheduled_at,
                fire_at,
                offset,
                email,
                role,
            ))

    if not rows:
        log.info("reminder: %s — all offsets in the past, nothing scheduled", booking.cal_booking_uid)
        return 0

    # Idempotency: re-receiving the same BOOKING_CREATED (rare; the
    # receiver dedupes on (uid, event_type) before we get here, but
    # belt-and-suspenders) must not duplicate rows. The UNIQUE on
    # (uid, offset_minutes, recipient_email) handles this.
    sql = """
        INSERT INTO reminder_jobs (
            cal_booking_uid, client_slug, booking_scheduled_at, fire_at,
            offset_minutes, recipient_email, recipient_role
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (cal_booking_uid, offset_minutes, recipient_email) DO NOTHING
    """
    inserted = 0
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                for row in rows:
                    cur.execute(sql, row)
                    inserted += cur.rowcount  # 0 if conflict, 1 if inserted
            conn.commit()
    except Exception as exc:  # noqa: BLE001
        log.warning("reminder: schedule_on_created failed for %s: %s", booking.cal_booking_uid, exc)
        return 0

    log.info(
        "reminder: scheduled %d row(s) for booking %s (offsets=%s, recipients=%s)",
        inserted, booking.cal_booking_uid,
        [r[4] for r in rows], [r[6] for r in rows],
    )
    return inserted


def cancel_for_uid(pool: ConnectionPool, cal_booking_uid: str) -> int:
    """Mark all *pending* rows for this booking as cancelled.

    Sent/failed rows are left alone — they're history.
    """
    if not cal_booking_uid:
        return 0
    sql = """
        UPDATE reminder_jobs
           SET status = 'cancelled',
               last_attempt_at = NOW()
         WHERE cal_booking_uid = %s
           AND status = 'pending'
    """
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (cal_booking_uid,))
                n = cur.rowcount
            conn.commit()
    except Exception as exc:  # noqa: BLE001
        log.warning("reminder: cancel_for_uid failed for %s: %s", cal_booking_uid, exc)
        return 0
    if n:
        log.info("reminder: cancelled %d pending row(s) for booking %s", n, cal_booking_uid)
    return n


def reschedule_for_uid(
    pool: ConnectionPool,
    booking: ExtractedBooking,
    raw_payload: dict,
) -> int:
    """Handle a BOOKING_RESCHEDULED event.

    cal.diy's reschedule semantics:
      - A *new* uid is minted for the rescheduled booking
      - `payload.rescheduleUid` carries the *original* uid
      - The new booking arrives as BOOKING_RESCHEDULED (separate from
        BOOKING_CREATED — the platform fires this trigger specifically)

    Strategy: cancel pending rows under the previous uid, then schedule
    fresh rows under the new uid using the same code path as a creation.
    Simpler than UPDATE'ing in place and handles edge cases like the
    previous booking having different recipients due to a config change
    that landed between create and reschedule.
    """
    previous = booking.previous_uid
    if previous:
        cancel_for_uid(pool, previous)
    return schedule_on_created(pool, booking, raw_payload)
