"""Reminder config + status read/write against receiver-DB.

Two surfaces:

- `get_config` / `set_config` for the per-client policy stored in
  `client_reminder_config`. Writes happen from admin-api routes when the
  operator edits the Reminders card in the admin-ui.
- `counts_per_uid` / `pending_in_window` for the dashboard + detail-page
  status display. Pure reads; receiver's worker is the only writer to
  `reminder_jobs` (besides the scheduler, which is also receiver-side).

Defaults: when no per-client row exists, the dataclass returned by
get_config carries the receiver's env-derived defaults so the UI can show
"using global default" vs "overridden". Mirrors what the receiver does at
schedule time — both sides have the same fallback policy.

Important: admin-api uses RECEIVER_DB_URL for *both* reads and writes
against this table. The connection user must therefore have INSERT/UPDATE
permission on `client_reminder_config`. The default Fly attach gives full
access; if you're using a read-only role (per RUNBOOK option B), grant
INSERT/UPDATE on client_reminder_config to that role too.
"""
from __future__ import annotations

import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from psycopg_pool import ConnectionPool

log = logging.getLogger(__name__)

VALID_ROLES = ("prospect", "host", "agency")
_DEFAULT_OFFSETS = (60,)                              # one hour
_DEFAULT_RECIPIENTS = ("prospect", "host", "agency")  # everyone, opt-out


@dataclass(frozen=True)
class ReminderConfig:
    offsets_min: tuple[int, ...]
    recipients: tuple[str, ...]
    is_default: bool             # True when no per-client row exists
    updated_at: datetime | None  # None when is_default=True

    def to_dict(self) -> dict[str, Any]:
        return {
            "offsets_min": list(self.offsets_min),
            "recipients": list(self.recipients),
            "is_default": self.is_default,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


def _default_offsets() -> tuple[int, ...]:
    raw = os.environ.get("REMINDER_OFFSETS_MIN")
    if raw is None:
        return _DEFAULT_OFFSETS
    out: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            n = int(part)
        except ValueError:
            continue
        if n > 0:
            out.append(n)
    return tuple(out)


def _default_recipients() -> tuple[str, ...]:
    raw = os.environ.get("REMINDER_RECIPIENTS")
    if raw is None:
        return _DEFAULT_RECIPIENTS
    out: list[str] = []
    for r in raw.split(","):
        role = r.strip().lower()
        if role in VALID_ROLES and role not in out:
            out.append(role)
    return tuple(out)


def get_config(pool: ConnectionPool | None, client_slug: str) -> ReminderConfig:
    """Return the resolved config for one client.

    Falls back to env defaults when:
      - the pool is absent
      - no row exists for this slug
      - the DB lookup fails (logged)
    """
    fallback = ReminderConfig(
        offsets_min=_default_offsets(),
        recipients=_default_recipients(),
        is_default=True,
        updated_at=None,
    )
    if pool is None or not client_slug:
        return fallback
    sql = """
        SELECT offsets_min, recipients, updated_at
          FROM client_reminder_config
         WHERE client_slug = %s
    """
    try:
        with pool.connection() as conn, conn.cursor() as cur:
            cur.execute(sql, (client_slug,))
            row = cur.fetchone()
    except Exception as exc:  # noqa: BLE001
        log.warning("reminder config: lookup failed for %s (%s)", client_slug, exc)
        return fallback

    if not row:
        return fallback
    offsets, recipients, updated_at = row
    return ReminderConfig(
        offsets_min=tuple(int(x) for x in (offsets or []) if int(x) > 0),
        recipients=tuple(r for r in (recipients or []) if r in VALID_ROLES),
        is_default=False,
        updated_at=updated_at,
    )


def set_config(
    pool: ConnectionPool | None,
    client_slug: str,
    *,
    offsets_min: list[int],
    recipients: list[str],
) -> ReminderConfig:
    """UPSERT the per-client policy. Returns the freshly-stored config.

    Validates + normalizes inputs:
      - offsets: positive ints only, deduped, sorted desc (rendering nicety)
      - recipients: VALID_ROLES only, deduped, original-order preserved
      - empty offsets OR empty recipients is allowed (means "disabled for
        this client") — the receiver short-circuits on either being empty
    """
    if pool is None:
        raise RuntimeError("reminders DB pool unavailable; cannot write config")

    clean_offsets = sorted({int(x) for x in offsets_min if int(x) > 0}, reverse=True)
    clean_recipients: list[str] = []
    for r in recipients:
        rr = r.strip().lower()
        if rr in VALID_ROLES and rr not in clean_recipients:
            clean_recipients.append(rr)

    sql = """
        INSERT INTO client_reminder_config (client_slug, offsets_min, recipients, updated_at)
        VALUES (%s, %s, %s, NOW())
        ON CONFLICT (client_slug) DO UPDATE
           SET offsets_min = EXCLUDED.offsets_min,
               recipients  = EXCLUDED.recipients,
               updated_at  = NOW()
        RETURNING offsets_min, recipients, updated_at
    """
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (client_slug, clean_offsets, clean_recipients))
        row = cur.fetchone()
        conn.commit()
    if not row:
        # ON CONFLICT DO UPDATE should always RETURN, but defensively:
        raise RuntimeError("upsert returned no row")
    offsets, recipients_out, updated_at = row
    log.info(
        "reminder config: upserted %s — offsets=%s recipients=%s",
        client_slug, offsets, recipients_out,
    )
    return ReminderConfig(
        offsets_min=tuple(offsets or ()),
        recipients=tuple(recipients_out or ()),
        is_default=False,
        updated_at=updated_at,
    )


def counts_per_uid(pool: ConnectionPool | None, client_slug: str) -> dict[str, dict[str, int]]:
    """Per-booking status counts for the detail page.

    Returns: { cal_booking_uid: { pending, processing, sent, failed, cancelled } }

    Missing statuses default to 0. Used to render the small reminder
    summary next to each booking row.
    """
    if pool is None or not client_slug:
        return {}
    sql = """
        SELECT cal_booking_uid, status, COUNT(*)::int
          FROM reminder_jobs
         WHERE client_slug = %s
         GROUP BY cal_booking_uid, status
    """
    out: dict[str, dict[str, int]] = {}
    try:
        with pool.connection() as conn, conn.cursor() as cur:
            cur.execute(sql, (client_slug,))
            for uid, status, n in cur.fetchall():
                bucket = out.setdefault(uid, {
                    "pending": 0, "processing": 0, "sent": 0,
                    "failed": 0, "cancelled": 0,
                })
                if status in bucket:
                    bucket[status] = n
    except Exception as exc:  # noqa: BLE001
        log.warning("reminder counts_per_uid failed for %s: %s", client_slug, exc)
        return {}
    return out


def pending_in_window(pool: ConnectionPool | None, *, window_hours: int = 24) -> int:
    """Total pending reminders due within `window_hours`. Powers the
    dashboard stat card. 0 when the pool is absent."""
    if pool is None:
        return 0
    sql = f"""
        SELECT COUNT(*)::int
          FROM reminder_jobs
         WHERE status = 'pending'
           AND fire_at <= NOW() + INTERVAL '{int(window_hours)} hours'
    """
    try:
        with pool.connection() as conn, conn.cursor() as cur:
            cur.execute(sql)
            row = cur.fetchone()
    except Exception as exc:  # noqa: BLE001
        log.warning("reminder pending_in_window failed: %s", exc)
        return 0
    return int(row[0]) if row else 0


def aggregate_status(pool: ConnectionPool | None) -> dict[str, int]:
    """Cross-client totals. Powers the dashboard breakdown."""
    if pool is None:
        return {"pending": 0, "processing": 0, "sent": 0, "failed": 0, "cancelled": 0}
    sql = "SELECT status, COUNT(*)::int FROM reminder_jobs GROUP BY status"
    out = {"pending": 0, "processing": 0, "sent": 0, "failed": 0, "cancelled": 0}
    try:
        with pool.connection() as conn, conn.cursor() as cur:
            cur.execute(sql)
            for status, n in cur.fetchall():
                if status in out:
                    out[status] = n
    except Exception as exc:  # noqa: BLE001
        log.warning("reminder aggregate_status failed: %s", exc)
    return out
