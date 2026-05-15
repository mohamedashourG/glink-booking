"""External-target fan-out, run as a background task after the 2xx returns.

Contract:
- Runs ONLY for newly-stored rows. cal.diy retries (deduped by the DB's
  UNIQUE constraint) must not double-post.
- Each integration is independent: a failure or hang in one MUST NOT
  affect the others, the DB row, or the response. We `asyncio.gather`
  them with `return_exceptions=True` and never re-raise.
- The DB row is the durability anchor. Known limitation: if the
  receiver crashes between the 2xx and this background task running,
  this booking's external dispatch is lost. The row is still on disk,
  so a future replay tool can re-fire — out of scope for now.
"""
from __future__ import annotations

import asyncio
import logging

from psycopg_pool import ConnectionPool

from receiver.extract import ExtractedBooking
from receiver.integrations import email as email_integration
from receiver.integrations import hubspot as hubspot_integration
from receiver.integrations import sheets as sheets_integration
from receiver.integrations import slack as slack_integration

log = logging.getLogger(__name__)


_INTEGRATIONS = (
    ("slack", slack_integration),
    ("hubspot", hubspot_integration),
    ("email", email_integration),
    ("sheets", sheets_integration),
)


async def _safe_dispatch(name: str, mod, booking: ExtractedBooking, raw_payload: dict, pool: ConnectionPool) -> None:
    try:
        await mod.dispatch(booking, raw_payload, pool=pool)
    except Exception:
        log.exception("fanout: %s integration raised for booking %s", name, booking.cal_booking_uid)


async def dispatch_external(
    booking: ExtractedBooking,
    raw_payload: dict,
    *,
    pool: ConnectionPool,
) -> None:
    """Run all configured integrations concurrently. Always returns; never raises."""
    coros = [_safe_dispatch(name, mod, booking, raw_payload, pool) for name, mod in _INTEGRATIONS]
    await asyncio.gather(*coros, return_exceptions=True)
    log.info("fanout: completed for booking %s (%s)", booking.cal_booking_uid, booking.event_type)


def configured_integrations() -> list[str]:
    """Names of integrations that have credentials in env (for startup logging)."""
    return [name for name, mod in _INTEGRATIONS if mod.is_configured()]
