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
