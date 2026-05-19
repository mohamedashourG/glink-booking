"""Reminder policy — env defaults + per-client overrides.

Defaults live in env vars on the receiver:

  REMINDER_OFFSETS_MIN   — comma-separated minutes-before (e.g. "60" or
                           "1440,60,15"). Empty disables the feature
                           globally.
  REMINDER_RECIPIENTS    — comma-separated subset of {prospect,host,agency}.
                           Default: prospect,host,agency.
  REMINDER_TICK_SECONDS  — worker poll interval. Default 30.

Per-client overrides live in `client_reminder_config` (see schema.sql),
written by admin-api when the operator edits the Reminders card in the
admin-ui. The scheduler prefers the per-client row when present, falls
back to env defaults when absent.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Iterable

from psycopg_pool import ConnectionPool

log = logging.getLogger(__name__)

# Roles that map to a real email address at send time. Anything else is
# ignored — keeps a typo in admin-ui from creating orphan rows.
VALID_ROLES = ("prospect", "host", "agency")


@dataclass(frozen=True)
class ReminderPolicy:
    """Resolved policy for one client.

    `offsets_min` is intentionally a tuple (immutable) so it can be safely
    shared across calls. Empty tuple = the feature is off for this client.
    """
    offsets_min: tuple[int, ...]
    recipients: tuple[str, ...]


def _parse_int_csv(s: str | None) -> tuple[int, ...]:
    """Parse "60,1440" → (60, 1440). Silently drops anything non-positive.

    Defensive against admin-ui forms that may pass strings; the route
    layer should validate first, but a bad value should still degrade
    gracefully (skip that offset) instead of crashing the worker.
    """
    if not s:
        return ()
    out: list[int] = []
    for part in s.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            n = int(part)
        except ValueError:
            log.warning("reminder offset ignored — not an int: %r", part)
            continue
        if n <= 0:
            continue
        out.append(n)
    return tuple(out)


def _parse_role_csv(s: str | None) -> tuple[str, ...]:
    """Parse "prospect,host" → ("prospect","host"). Filters to VALID_ROLES."""
    if not s:
        return ()
    seen: list[str] = []
    for raw in s.split(","):
        role = raw.strip().lower()
        if not role:
            continue
        if role not in VALID_ROLES:
            log.warning("reminder recipient ignored — not a known role: %r", role)
            continue
        if role not in seen:  # preserve order, dedupe
            seen.append(role)
    return tuple(seen)


def env_default_policy() -> ReminderPolicy:
    """The fallback policy when no per-client row exists."""
    offsets = _parse_int_csv(os.environ.get("REMINDER_OFFSETS_MIN", "60"))
    recipients = _parse_role_csv(
        os.environ.get("REMINDER_RECIPIENTS", "prospect,host,agency"),
    )
    return ReminderPolicy(offsets_min=offsets, recipients=recipients)


def policy_for_client(pool: ConnectionPool, client_slug: str | None) -> ReminderPolicy:
    """Look up the per-client policy. Falls back to env defaults if absent.

    Reads the `client_reminder_config` table by client_slug. NULL slug or
    no matching row returns the env policy unchanged.
    """
    default = env_default_policy()
    if not client_slug:
        return default

    sql = """
        SELECT offsets_min, recipients
          FROM client_reminder_config
         WHERE client_slug = %s
    """
    try:
        with pool.connection() as conn, conn.cursor() as cur:
            cur.execute(sql, (client_slug,))
            row = cur.fetchone()
    except Exception as exc:  # noqa: BLE001
        log.warning("reminder: policy lookup failed for %s (%s); using env defaults", client_slug, exc)
        return default

    if not row:
        return default
    offsets, recipients = row
    # Postgres ARRAY → Python list; both already-typed. Coerce to tuple
    # for the same immutability guarantee as the env path.
    return ReminderPolicy(
        offsets_min=tuple(int(x) for x in (offsets or []) if int(x) > 0),
        recipients=tuple(r for r in (recipients or []) if r in VALID_ROLES),
    )


def tick_seconds() -> int:
    """How often the worker polls. Floor of 5s so a typo can't burn CPU."""
    raw = os.environ.get("REMINDER_TICK_SECONDS", "30")
    try:
        n = int(raw)
    except ValueError:
        return 30
    return max(5, n)


def agency_email() -> str | None:
    """Where the agency reminder goes. Reuses the existing fan-out env.

    Returns None if not configured — agency recipients simply skip in that
    case (same shape as the existing email fan-out).
    """
    return os.environ.get("AGENCY_NOTIFY_EMAIL") or None


def is_enabled() -> bool:
    """True if at least one offset is configured. Used to short-circuit
    the worker and scheduler when the feature is fully disabled."""
    return bool(env_default_policy().offsets_min)


# Helper used by callers that want to render the per-recipient resolution
# in a single place (e.g. logging at schedule time, or the admin-ui status).
def resolve_recipients(
    policy: ReminderPolicy,
    *,
    prospect_email: str | None,
    host_email: str | None,
) -> list[tuple[str, str]]:
    """Return [(role, email), ...] for the recipients we can actually email.

    Roles whose email is missing are dropped silently. Caller can compare
    the returned count to len(policy.recipients) to spot misconfigured
    clients (e.g. agency role enabled but AGENCY_NOTIFY_EMAIL unset).
    """
    out: list[tuple[str, str]] = []
    for role in policy.recipients:
        email = {
            "prospect": prospect_email,
            "host": host_email,
            "agency": agency_email(),
        }.get(role)
        if email:
            out.append((role, email))
    return out
