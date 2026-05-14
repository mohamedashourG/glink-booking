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
    -- Dedup retries from cal.diy: same booking + same trigger = same notification.
    UNIQUE (cal_booking_uid, event_type)
);

CREATE INDEX IF NOT EXISTS bookings_client_slug_idx  ON bookings (client_slug);
CREATE INDEX IF NOT EXISTS bookings_received_at_idx  ON bookings (received_at DESC);
