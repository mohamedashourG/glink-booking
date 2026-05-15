"""Authenticate against cal.diy's NextAuth credentials endpoint and verify
the user is the system admin.

Reuses cal_client.cal_web.login() to do the actual login (CSRF + credentials
callback). The role check then GETs cal.diy's /api/auth/session through the
authenticated cookie jar — that endpoint surfaces the user's role (and a
reason like "2fa" when an admin's privileges are gated).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from cal_client.cal_web import CalWebError, login

log = logging.getLogger(__name__)

# Both ADMIN and INACTIVE_ADMIN denote a user with the admin row-level role.
# INACTIVE_ADMIN means the role is downgraded inside cal.diy (e.g. because
# the admin hasn't enabled 2FA yet) — they're still the system administrator,
# we just can't depend on every cal.diy admin-feature being usable. For the
# admin-ui's purposes (read manifest, run our own provisioning), that's fine.
ADMIN_ROLES = frozenset({"ADMIN", "INACTIVE_ADMIN"})


@dataclass(frozen=True)
class CalAdminUser:
    email: str
    role: str
    name: str | None
    inactive_admin_reason: str | None  # e.g. "2fa" when role=INACTIVE_ADMIN


def authenticate_admin(cal_web_base: str, *, email: str, password: str) -> CalAdminUser | None:
    """Verify cal.diy credentials AND that the user has an admin role.

    Returns the CalAdminUser on success; None on bad-credentials OR not-admin
    (the caller should not distinguish — the API surfaces a single generic
    401 either way).
    """
    try:
        session = login(cal_web_base, email=email, password=password)
    except CalWebError as exc:
        log.info("admin login: cal.diy login rejected for %s (%s)", email, exc)
        return None

    with session:
        try:
            resp = session.client.get(f"{cal_web_base}/api/auth/session", timeout=10.0)
        except httpx.HTTPError as exc:
            log.warning("admin login: /api/auth/session network error for %s: %s", email, exc)
            return None

    if resp.status_code != 200:
        log.warning("admin login: /api/auth/session returned %s for %s", resp.status_code, email)
        return None

    try:
        data = resp.json()
    except ValueError:
        return None

    user = data.get("user") if isinstance(data, dict) else None
    if not isinstance(user, dict):
        return None

    role = str(user.get("role") or "")
    if role not in ADMIN_ROLES:
        log.info("admin login: %s has role=%s (not admin)", email, role)
        return None

    return CalAdminUser(
        email=str(user.get("email") or email),
        role=role,
        name=user.get("name"),
        inactive_admin_reason=user.get("inactiveAdminReason"),
    )
