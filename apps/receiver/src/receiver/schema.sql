-- Source-of-truth bookings ledger for the receiver.
-- One row per webhook delivery; raw_payload always populated as the safety net.

CREATE TABLE IF NOT EXISTS bookings (
    id                       BIGSERIAL PRIMARY KEY,
    cal_booking_uid          TEXT        NOT NULL,
    event_type               TEXT        NOT NULL,
    client_slug              TEXT,
    prospect_name            TEXT,
    prospect_email           TEXT,
    prospect_company         TEXT,
    scheduled_at             TIMESTAMPTZ,
    timezone                 TEXT,
    video_link               TEXT,
    utm_source               TEXT,
    utm_medium               TEXT,
    utm_campaign             TEXT,
    utm_content              TEXT,
    utm_term                 TEXT,
    custom_responses_json    JSONB,
    raw_payload_json         JSONB       NOT NULL,
    received_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Dedup retries from bookings@glnkco.com: same booking + same trigger = same notification.
    UNIQUE (cal_booking_uid, event_type)
);

CREATE INDEX IF NOT EXISTS bookings_client_slug_idx  ON bookings (client_slug);
CREATE INDEX IF NOT EXISTS bookings_received_at_idx  ON bookings (received_at DESC);

-- Lifecycle tracking for the HubSpot meeting engagement: created on the first
-- BOOKING_CREATED row for a given uid, then reused on RESCHEDULED/CANCELLED so
-- we update the SAME meeting instead of duplicating. Lookup is via the latest
-- row for that uid that has a non-null hubspot_meeting_id.
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS hubspot_meeting_id TEXT;
CREATE INDEX IF NOT EXISTS bookings_uid_hsmeeting_idx
    ON bookings (cal_booking_uid)
    WHERE hubspot_meeting_id IS NOT NULL;

-- ── Pre-meeting reminders ──────────────────────────────────────────────────
-- Captured from the webhook payload's `organizer.email`. Used at reminder-
-- send time so we can email the host without re-parsing raw_payload_json.
-- NULL on historical rows; the email integration skips host reminders when
-- this is missing.
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS host_email TEXT;

-- Per-client reminder policy. One row per client_slug. Written by admin-api
-- (via PUT /clients/<slug>/reminders) and at provision time. Read by the
-- receiver's scheduler on every BOOKING_CREATED.
--   offsets_min: array of minutes-before-meeting at which to fire reminders
--                (e.g. {60} for one hour, {1440,60} for one day + one hour)
--   recipients:  subset of {'prospect','host','agency'}
CREATE TABLE IF NOT EXISTS client_reminder_config (
    client_slug   TEXT PRIMARY KEY,
    offsets_min   INTEGER[] NOT NULL,
    recipients    TEXT[]    NOT NULL,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- The reminder job queue. One row per (booking × offset × recipient).
-- The worker polls for `status='pending' AND fire_at <= NOW()`, claims a
-- batch with FOR UPDATE SKIP LOCKED so multiple HA workers don't double-fire.
--
-- Statuses:
--   pending    — waiting for fire_at
--   processing — claimed by a worker, in flight (must reset if stuck >5min)
--   sent       — Resend accepted (sent_at populated)
--   failed     — exceeded retry budget; last_error captures why
--   cancelled  — meeting cancelled/rejected, OR offset became negative after a
--                reschedule landed the meeting closer than the offset
CREATE TABLE IF NOT EXISTS reminder_jobs (
    id                    BIGSERIAL PRIMARY KEY,
    cal_booking_uid       TEXT        NOT NULL,
    client_slug           TEXT,
    booking_scheduled_at  TIMESTAMPTZ NOT NULL,
    fire_at               TIMESTAMPTZ NOT NULL,
    offset_minutes        INTEGER     NOT NULL,
    recipient_email       TEXT        NOT NULL,
    recipient_role        TEXT        NOT NULL,   -- prospect | host | agency
    status                TEXT        NOT NULL DEFAULT 'pending',
    attempts              INTEGER     NOT NULL DEFAULT 0,
    last_error            TEXT,
    last_attempt_at       TIMESTAMPTZ,
    sent_at               TIMESTAMPTZ,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Idempotency: re-running scheduler for the same (booking, offset, recipient)
    -- can't double-insert. Crucial because a RESCHEDULED webhook may arrive
    -- before we've processed CANCELLED for the same uid.
    UNIQUE (cal_booking_uid, offset_minutes, recipient_email)
);

-- Partial index: only pending rows are polled by the worker. Keeps the
-- index small even after years of sent/failed history accumulates.
CREATE INDEX IF NOT EXISTS reminder_jobs_due_idx
    ON reminder_jobs (fire_at)
    WHERE status = 'pending';

-- Lookup by uid is needed for reschedule/cancel — both rewrite multiple rows
-- by cal_booking_uid.
CREATE INDEX IF NOT EXISTS reminder_jobs_uid_idx
    ON reminder_jobs (cal_booking_uid);
