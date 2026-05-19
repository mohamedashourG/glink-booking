"""Read-only Postgres connection pools for the "live data" features.

admin-api needs to look at two other databases that the deploy already owns:

- **cal.diy** (`glnk_booking`) — to fetch each client's *current* username,
  so the dashboard reflects edits the user made in cal.diy directly. Without
  this, the manifest's stored `slug` silently drifts when a user changes
  their username on their own.
- **receiver** (`glnk_receiver`) — to count booking rows per client and
  surface the recent-meeting history on the detail page. The receiver
  doesn't expose an HTTP read API; admin-api goes straight to its DB.

Both connections are **read-only by intent** — no module in admin-api should
issue writes against either pool. (Enforced by convention here; for hard
enforcement create a dedicated `*_ro` Postgres role with only SELECT.)

Both pools are **optional**. When the env vars are unset:

- `/clients` falls back to manifest-only data (no live username, no counts).
- `/clients/{slug}` returns an empty bookings list.
- `/slug-available` reports cal.diy unknown (admin-ui still does the
  local-manifest check, so adding clients still warns on duplicates).

Pools are opened in the FastAPI lifespan and stored on `app.state`. Reach
them via `request.app.state.cal_pool` / `request.app.state.receiver_pool`
(may be `None`).
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator

from psycopg_pool import ConnectionPool

log = logging.getLogger(__name__)


def open_optional_pool(label: str, conninfo: str | None) -> ConnectionPool | None:
    """Open a pool if `conninfo` is set; else log and return None.

    Failures during open() are logged and swallowed (admin-api stays up;
    features that need the pool degrade gracefully). The alternative —
    crashing the app — would knock the admin-ui offline if either DB is
    briefly unreachable, which is worse than degraded features.
    """
    if not conninfo:
        log.info("%s pool: skipped (env var unset; live features for this DB disabled)", label)
        return None
    try:
        # min_size=0 so we don't dial out at boot; max_size kept small —
        # admin-api is low-concurrency (a single operator).
        pool = ConnectionPool(conninfo, min_size=0, max_size=4, open=True, timeout=10)
        log.info("%s pool: opened", label)
        return pool
    except Exception as exc:  # noqa: BLE001
        log.warning("%s pool: failed to open (%s) — live features for this DB disabled", label, exc)
        return None


def close_pool(label: str, pool: ConnectionPool | None) -> None:
    if pool is None:
        return
    try:
        pool.close()
        log.info("%s pool: closed", label)
    except Exception as exc:  # noqa: BLE001
        log.warning("%s pool: error during close (%s)", label, exc)


@contextmanager
def borrow(pool: ConnectionPool | None) -> Iterator[object | None]:
    """Yield a connection or None when the pool is absent.

    Lets call sites write `with borrow(pool) as conn: ...` and treat the
    None case as "feature disabled" without branching on pool truthiness.
    """
    if pool is None:
        yield None
        return
    with pool.connection() as conn:
        yield conn
