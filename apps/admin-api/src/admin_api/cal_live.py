"""Live reads against cal.diy's database (`glnk_booking`).

We avoid this when we can — cal.diy's API would be the "proper" surface —
but cal.diy doesn't expose an admin-listing endpoint we can call, and
querying the DB is dramatically simpler than scraping a paginated UI or
logging in as each user one at a time.

Everything in this module is **read-only**. Writes belong in
`cal_client.cal_web` (which goes through cal.diy's tRPC, so cal.diy's own
hooks fire — important for things like cache invalidation).

If you find yourself needing data from another cal.diy table here, prefer
adding a function next to this one (small, focused queries) rather than
exposing a generic execute() — keeps the read surface enumerable.
"""
from __future__ import annotations

import logging

from psycopg_pool import ConnectionPool

log = logging.getLogger(__name__)


def list_usernames(pool: ConnectionPool | None) -> dict[str, str]:
    """Map lowercased email → current cal.diy username.

    The admin row is included; callers that only care about clients can
    filter by role themselves. We keep this generic so a future "is this
    slug taken by the admin?" check doesn't have to re-query.

    Returns an empty dict when the pool is absent so callers can treat
    "no data" and "no overlap" identically.
    """
    if pool is None:
        return {}
    rows: list[tuple[str, str | None]]
    try:
        with pool.connection() as conn, conn.cursor() as cur:
            cur.execute('SELECT lower(email), username FROM users')
            rows = cur.fetchall()
    except Exception as exc:  # noqa: BLE001
        log.warning("cal.diy username lookup failed: %s", exc)
        return {}
    # username can be NULL during signup. Skip those — drift detection
    # would otherwise flag every half-provisioned account as broken.
    return {email: uname for (email, uname) in rows if email and uname}


def is_username_taken(pool: ConnectionPool | None, candidate: str) -> bool | None:
    """Check whether a username already exists on cal.diy (case-insensitive).

    Returns:
        True  — taken (a row exists with this username, case-insensitive)
        False — definitely free
        None  — could not check (pool missing or query failed); callers
                should treat this as "unknown" rather than "free"

    The tri-state matters: the new-client form combines this with the
    local-manifest check, and "unknown" should not be reported as a green
    light to the operator.
    """
    if pool is None:
        return None
    needle = (candidate or "").strip().lower()
    if not needle:
        return False
    try:
        with pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                'SELECT 1 FROM users WHERE lower(username) = %s LIMIT 1',
                (needle,),
            )
            return cur.fetchone() is not None
    except Exception as exc:  # noqa: BLE001
        log.warning("cal.diy username check failed for %r: %s", candidate, exc)
        return None
