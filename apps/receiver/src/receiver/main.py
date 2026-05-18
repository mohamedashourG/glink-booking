"""FastAPI app exposing the bookings@glnkco.com webhook receiver."""
from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, Request, Response
from fastapi.responses import JSONResponse

from receiver import db, extract, fanout, signature
from receiver.config import load_settings

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

# Recognized bookings@glnkco.com event types. Anything else is a logged no-op (200 OK,
# nothing written) — per spec, unknown events are not errors.
_HANDLED_EVENT_TYPES = {
    "BOOKING_CREATED",
    "BOOKING_RESCHEDULED",
    "BOOKING_CANCELLED",
    "BOOKING_REJECTED",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings()
    pool = db.open_pool(settings.database_url)
    db.apply_schema(pool)
    app.state.settings = settings
    app.state.pool = pool
    configured = fanout.configured_integrations()
    log.info("receiver started — fan-out integrations configured: %s", configured or "(none)")
    try:
        yield
    finally:
        pool.close()
        log.info("receiver stopped")


app = FastAPI(lifespan=lifespan, title="glink-booking receiver")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks) -> Response:
    raw_body = await request.body()
    provided_sig = request.headers.get(signature.SIGNATURE_HEADER)

    if not signature.verify(request.app.state.settings.webhook_secret, raw_body, provided_sig):
        log.warning("webhook rejected: bad signature (header present=%s)", bool(provided_sig))
        return JSONResponse({"detail": "invalid signature"}, status_code=401)

    try:
        envelope = json.loads(raw_body)
    except ValueError:
        log.warning("webhook rejected: body is not valid JSON")
        return JSONResponse({"detail": "invalid json"}, status_code=400)

    if not isinstance(envelope, dict):
        return JSONResponse({"detail": "envelope must be a JSON object"}, status_code=400)

    event_type = envelope.get("triggerEvent")
    if event_type not in _HANDLED_EVENT_TYPES:
        log.info("ignoring unknown trigger '%s' (no-op, not an error)", event_type)
        return JSONResponse({"status": "ignored", "triggerEvent": event_type}, status_code=200)

    booking = extract.extract(envelope)

    if not booking.cal_booking_uid:
        # Without a uid we can't dedupe and the row would be lonely — but it's
        # still better to record it than silently drop. Use a synthetic key.
        booking.cal_booking_uid = f"missing-uid-{event_type}-{hash(raw_body)}"
        log.warning("payload had no booking uid; stored under synthetic key %s", booking.cal_booking_uid)

    # Postgres write is the priority operation. Any failure here propagates as
    # a 500 so bookings@glnkco.com retries — which is exactly what we want for durability.
    pool = request.app.state.pool
    inserted = db.insert_booking(pool, booking, envelope)

    if inserted:
        log.info(
            "stored %s booking %s (client=%s)",
            booking.event_type, booking.cal_booking_uid, booking.client_slug,
        )
        # Fan-out runs as a background task AFTER the 2xx is sent. bookings@glnkco.com
        # gets a fast response; integrations take their time. Fires only on
        # newly-stored rows, never on a dedup hit (so retries don't double-
        # post to Slack/HubSpot/email).
        background_tasks.add_task(fanout.dispatch_external, booking, envelope, pool=pool)
    else:
        log.info(
            "duplicate %s for booking %s ignored (already on disk; fan-out skipped)",
            booking.event_type, booking.cal_booking_uid,
        )

    return JSONResponse({"status": "ok", "stored": inserted}, status_code=200)
