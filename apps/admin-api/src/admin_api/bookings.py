"""Read-only aggregations and lookups against the receiver's `bookings` table.

The receiver stores **one row per webhook delivery**, so a single meeting
(identified by `cal_booking_uid`) usually appears multiple times — once as
BOOKING_CREATED, then maybe BOOKING_RESCHEDULED, then BOOKING_CANCELLED, etc.

For the dashboard we don't want to count those repeats as separate meetings.
"Latest event per uid" is the meaningful unit, computed with `DISTINCT ON`
ordered by descending row id (the autoincrement is a stable proxy for
arrival order — and bookings@glnkco.com may deliver out of order, but the
last-arrived event still represents the operator's most recent view).

Everything in this module returns empty/None when the pool is absent;
admin-api degrades to "no booking data shown" rather than 500ing.
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from psycopg_pool import ConnectionPool

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ClientCounts:
    total: int
    created: int
    rescheduled: int
    cancelled: int
    rejected: int
    last_at: datetime | None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["last_at"] = self.last_at.isoformat() if self.last_at else None
        return d


_ZERO = ClientCounts(total=0, created=0, rescheduled=0, cancelled=0, rejected=0, last_at=None)


@dataclass(frozen=True)
class BookingRow:
    cal_booking_uid: str
    current_event: str  # the most recent event_type for this uid
    prospect_name: str | None
    prospect_email: str | None
    prospect_company: str | None
    scheduled_at: datetime | None
    timezone: str | None
    video_link: str | None
    received_at: datetime

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["scheduled_at"] = self.scheduled_at.isoformat() if self.scheduled_at else None
        d["received_at"] = self.received_at.isoformat()
        return d


def counts_per_client(pool: ConnectionPool | None) -> dict[str, ClientCounts]:
    """Map client_slug → ClientCounts. Empty dict when pool is absent.

    Rows with NULL client_slug (legacy payloads where extraction couldn't
    pin a slug) are silently dropped. They're tiny in practice and would
    only confuse the per-client view.
    """
    if pool is None:
        return {}
    sql = """
        WITH latest AS (
            SELECT DISTINCT ON (cal_booking_uid)
                cal_booking_uid, client_slug, event_type, received_at
            FROM bookings
            ORDER BY cal_booking_uid, id DESC
        )
        SELECT
            client_slug,
            COUNT(*)::int                                                  AS total,
            COUNT(*) FILTER (WHERE event_type = 'BOOKING_CREATED')::int    AS created,
            COUNT(*) FILTER (WHERE event_type = 'BOOKING_RESCHEDULED')::int AS rescheduled,
            COUNT(*) FILTER (WHERE event_type = 'BOOKING_CANCELLED')::int  AS cancelled,
            COUNT(*) FILTER (WHERE event_type = 'BOOKING_REJECTED')::int   AS rejected,
            MAX(received_at)                                               AS last_at
        FROM latest
        WHERE client_slug IS NOT NULL
        GROUP BY client_slug
    """
    out: dict[str, ClientCounts] = {}
    try:
        with pool.connection() as conn, conn.cursor() as cur:
            cur.execute(sql)
            for slug, total, created, rescheduled, cancelled, rejected, last_at in cur.fetchall():
                out[slug] = ClientCounts(
                    total=total,
                    created=created,
                    rescheduled=rescheduled,
                    cancelled=cancelled,
                    rejected=rejected,
                    last_at=last_at,
                )
    except Exception as exc:  # noqa: BLE001
        log.warning("counts_per_client failed: %s — returning empty counts", exc)
        return {}
    return out


def counts_for_slug(pool: ConnectionPool | None, slug: str) -> ClientCounts:
    """Counts for a single client. Returns the zero record when unknown
    (no pool, no rows, or DB error) — keeps detail-page rendering simple."""
    if not slug:
        return _ZERO
    counts = counts_per_client(pool)
    return counts.get(slug, _ZERO)


def list_for_client(pool: ConnectionPool | None, slug: str, *, limit: int = 200) -> list[BookingRow]:
    """Most recent bookings for a client (one row per cal_booking_uid).

    Ordered by scheduled time descending; falls back to received_at for
    rows that lack a scheduled_at (e.g. CANCELLED without a future time).
    `limit` caps the response so a long-running client doesn't blow up
    the detail page.
    """
    if pool is None or not slug:
        return []
    sql = """
        WITH latest AS (
            SELECT DISTINCT ON (cal_booking_uid)
                cal_booking_uid, event_type, prospect_name, prospect_email,
                prospect_company, scheduled_at, timezone, video_link, received_at
            FROM bookings
            WHERE client_slug = %s
            ORDER BY cal_booking_uid, id DESC
        )
        SELECT cal_booking_uid, event_type, prospect_name, prospect_email,
               prospect_company, scheduled_at, timezone, video_link, received_at
          FROM latest
         ORDER BY COALESCE(scheduled_at, received_at) DESC
         LIMIT %s
    """
    try:
        with pool.connection() as conn, conn.cursor() as cur:
            cur.execute(sql, (slug, limit))
            rows = cur.fetchall()
    except Exception as exc:  # noqa: BLE001
        log.warning("list_for_client failed for %r: %s — returning empty list", slug, exc)
        return []
    return [
        BookingRow(
            cal_booking_uid=uid,
            current_event=event,
            prospect_name=pname,
            prospect_email=pemail,
            prospect_company=pcompany,
            scheduled_at=sched,
            timezone=tz,
            video_link=video,
            received_at=received,
        )
        for (uid, event, pname, pemail, pcompany, sched, tz, video, received) in rows
    ]
