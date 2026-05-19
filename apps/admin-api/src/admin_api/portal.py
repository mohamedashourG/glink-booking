"""JWT-based handshake for the cal.diy → admin-ui iframe client portal.

Two distinct tokens flow through this module:

1. **`cal_token`** — minted by **cal.diy** server-side when it renders the
   Reminders tab for a logged-in user. Signed with the shared
   `PORTAL_JWT_SECRET`. Encodes `{slug, email, exp}` (and optionally `iss`
   for future multi-instance support). Short-lived (~5 min) so a leaked
   URL can't be replayed for long.

2. **`portal_session`** — minted by **admin-api** after verifying a
   cal_token. Signed with the same secret (separate `typ` claim so the
   two never confuse). Carries `{slug, email, exp}` and is what the
   iframe's React code sends in the Authorization header on subsequent
   admin-api calls. TTL is `PORTAL_SESSION_TTL_SECONDS` (30 min default)
   so the editor stays usable while the iframe is open.

We intentionally avoid putting the session token in a cookie. The iframe
runs cross-origin from cal.diy, which means SameSite=None+Secure is
mandatory for cookies to ride along — easy in production (HTTPS both
sides), brittle in local dev (HTTP). Token-in-memory via the
Authorization header has no SameSite problem and is the standard pattern
for embedded React widgets.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import jwt

from admin_api.config import Settings

_ALG = "HS256"
_LEEWAY = 5
# Claim values used to namespace the two token shapes. Verifying one type
# refuses payloads tagged with the other, even when the signing secret is
# identical.
_TYP_INBOUND = "calportal.v1"   # what cal.diy mints
_TYP_SESSION = "session.v1"     # what we mint after exchange


@dataclass(frozen=True)
class PortalIdentity:
    """The bits admin-api needs after a successful verify."""
    slug: str
    email: str
    expires_at: int


class PortalDisabled(RuntimeError):
    """Raised when PORTAL_JWT_SECRET isn't configured."""


def verify_cal_token(settings: Settings, token: str) -> PortalIdentity | None:
    """Verify a JWT minted by cal.diy. Returns None on any failure
    (signature, expiry, missing claims, wrong typ).

    Callers should NOT distinguish the failure modes — leaking which
    check failed gives an attacker hints. Logging at the route layer is
    fine since logs aren't exposed."""
    if not settings.portal_jwt_secret:
        raise PortalDisabled("PORTAL_JWT_SECRET not configured")
    try:
        payload = jwt.decode(
            token,
            settings.portal_jwt_secret,
            algorithms=[_ALG],
            leeway=_LEEWAY,
            options={"require": ["exp", "slug", "email", "typ"]},
        )
    except jwt.PyJWTError:
        return None
    if payload.get("typ") != _TYP_INBOUND:
        return None
    slug = payload.get("slug")
    email = payload.get("email")
    if not isinstance(slug, str) or not slug:
        return None
    if not isinstance(email, str) or not email:
        return None
    return PortalIdentity(slug=slug, email=email, expires_at=int(payload["exp"]))


def issue_session(settings: Settings, identity: PortalIdentity) -> str:
    """Mint a portal session token. Same secret as the inbound token but
    tagged `typ=session.v1` so it can't be mistaken for one."""
    if not settings.portal_jwt_secret:
        raise PortalDisabled("PORTAL_JWT_SECRET not configured")
    now = int(time.time())
    payload: dict[str, Any] = {
        "typ": _TYP_SESSION,
        "slug": identity.slug,
        "email": identity.email,
        "iat": now,
        "exp": now + settings.portal_session_ttl_seconds,
    }
    return jwt.encode(payload, settings.portal_jwt_secret, algorithm=_ALG)


def verify_session(settings: Settings, token: str) -> PortalIdentity | None:
    """Verify a portal session token (what the iframe sends back).
    None on any failure."""
    if not settings.portal_jwt_secret:
        return None
    try:
        payload = jwt.decode(
            token,
            settings.portal_jwt_secret,
            algorithms=[_ALG],
            leeway=_LEEWAY,
            options={"require": ["exp", "slug", "email", "typ"]},
        )
    except jwt.PyJWTError:
        return None
    if payload.get("typ") != _TYP_SESSION:
        return None
    slug = payload.get("slug")
    email = payload.get("email")
    if not isinstance(slug, str) or not slug:
        return None
    if not isinstance(email, str) or not email:
        return None
    return PortalIdentity(slug=slug, email=email, expires_at=int(payload["exp"]))
