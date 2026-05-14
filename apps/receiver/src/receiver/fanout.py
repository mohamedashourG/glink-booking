"""External-target fan-out seam.

This module is INTENTIONALLY a no-op for now. The follow-up piece will
add real targets (Slack, HubSpot, transactional email, …) here.

Contract for future targets:

  - They receive the same `(ExtractedBooking, raw_payload)` tuple the DB
    insert just used.
  - They run AFTER the Postgres insert has succeeded — never before. The
    DB row is the durability anchor; external delivery is best-effort
    on top of that.
  - Their failures must NOT propagate into the HTTP response: cal.diy
    has already done its part once the row is on disk. Fan-out failures
    should be logged and (eventually) retried out-of-band.

Until those targets exist, dispatching is a logged no-op.
"""
from __future__ import annotations

import logging

from receiver.extract import ExtractedBooking

log = logging.getLogger(__name__)


def dispatch_external(booking: ExtractedBooking, raw_payload: dict) -> None:
    # No-op. Replace with parallel target dispatch when adding Slack / HubSpot / email.
    log.debug(
        "fanout: would dispatch %s for booking %s (no targets configured)",
        booking.event_type,
        booking.cal_booking_uid,
    )
