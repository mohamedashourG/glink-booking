"""Postgres I/O for the receiver."""
from __future__ import annotations

import json
import logging
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from receiver.extract import ExtractedBooking

log = logging.getLogger(__name__)

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def open_pool(database_url: str) -> ConnectionPool:
    pool = ConnectionPool(database_url, min_size=1, max_size=4, open=True, timeout=30)
    return pool


def apply_schema(pool: ConnectionPool) -> None:
    ddl = _SCHEMA_PATH.read_text()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(ddl)
        conn.commit()
    log.info("schema applied")


def insert_booking(
    pool: ConnectionPool,
    booking: ExtractedBooking,
    raw_payload: dict,
) -> bool:
    """Insert one booking row.

    Returns True if a new row was inserted, False if (cal_booking_uid,
    event_type) already existed (a duplicate retry from bookings@glnkco.com).

    Raises psycopg errors on real DB failures — callers should let the
    error bubble so the HTTP handler returns non-2xx and bookings@glnkco.com retries.
    """
    sql = """
        INSERT INTO bookings (
            cal_booking_uid,
            event_type,
            client_slug,
            prospect_name,
            prospect_email,
            prospect_company,
            scheduled_at,
            timezone,
            video_link,
            host_email,
            utm_source, utm_medium, utm_campaign, utm_content, utm_term,
            custom_responses_json,
            raw_payload_json
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s
        )
        ON CONFLICT (cal_booking_uid, event_type) DO NOTHING
        RETURNING id
    """
    params = (
        booking.cal_booking_uid,
        booking.event_type,
        booking.client_slug,
        booking.prospect_name,
        booking.prospect_email,
        booking.prospect_company,
        booking.scheduled_at,
        booking.timezone,
        booking.video_link,
        booking.host_email,
        booking.utm["utm_source"],
        booking.utm["utm_medium"],
        booking.utm["utm_campaign"],
        booking.utm["utm_content"],
        booking.utm["utm_term"],
        Jsonb(booking.custom_responses),
        Jsonb(raw_payload),
    )
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
        conn.commit()
    return row is not None


def find_hubspot_meeting_id(pool: ConnectionPool, cal_booking_uid: str) -> str | None:
    """Most recent HubSpot meeting id we've recorded for this booking, if any.

    Used by the HubSpot integration to reuse the same meeting across the
    BOOKING_CREATED → RESCHEDULED → CANCELLED lifecycle (so we update one
    record instead of creating a fresh meeting per event).
    """
    sql = """
        SELECT hubspot_meeting_id
          FROM bookings
         WHERE cal_booking_uid = %s
           AND hubspot_meeting_id IS NOT NULL
         ORDER BY id DESC
         LIMIT 1
    """
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (cal_booking_uid,))
            row = cur.fetchone()
    return row[0] if row else None


def set_hubspot_meeting_id(pool: ConnectionPool, cal_booking_uid: str, event_type: str, meeting_id: str) -> None:
    """Tag the (uid, event_type) row with the HubSpot meeting id we created/reused."""
    sql = """
        UPDATE bookings
           SET hubspot_meeting_id = %s
         WHERE cal_booking_uid = %s
           AND event_type = %s
    """
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (meeting_id, cal_booking_uid, event_type))
        conn.commit()
