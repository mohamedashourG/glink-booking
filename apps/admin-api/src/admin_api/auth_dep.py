"""FastAPI dependencies for protected routes.

Two auth identities are recognized:

- **Admin** — issued by /auth/login, carried as cookie OR Bearer header.
  Verified by `admin_api.session.verify_token`. Used by the admin-ui.
- **Portal session** — issued by /portal/exchange after a cal.diy JWT
  handshake. Carried as Bearer ONLY (no cookie — see admin_api.portal
  for why). Scoped to a single slug. Used by the iframe client portal.

The two never share an Authorization header — order of attempts is
admin-first, portal-second, so a stray admin token in a portal-only
route is treated as missing.
"""
from __future__ import annotations

from fastapi import HTTPException, Request, status

from admin_api.portal import PortalIdentity, verify_session as verify_portal_session
from admin_api.session import AdminSession, verify_token


def _extract_token(request: Request, cookie_name: str) -> str | None:
    auth = request.headers.get("Authorization") or request.headers.get("authorization")
    if auth and auth.lower().startswith("bearer "):
        return auth[7:].strip() or None
    return request.cookies.get(cookie_name)


def _bearer_only(request: Request) -> str | None:
    auth = request.headers.get("Authorization") or request.headers.get("authorization")
    if auth and auth.lower().startswith("bearer "):
        return auth[7:].strip() or None
    return None


def require_admin(request: Request) -> AdminSession:
    settings = request.app.state.settings
    raw = _extract_token(request, settings.session_cookie_name)
    if not raw:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not authenticated")
    session = verify_token(settings, raw)
    if session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or expired session")
    return session


def require_portal_session(request: Request) -> PortalIdentity:
    """Used by portal-only routes (e.g. GET /portal/me). Bearer-only."""
    settings = request.app.state.settings
    raw = _bearer_only(request)
    if not raw:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="portal session required")
    identity = verify_portal_session(settings, raw)
    if identity is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or expired portal session")
    return identity


def require_admin_or_portal_for_slug(slug: str):
    """Dependency factory: returns a route dependency that accepts EITHER
    an admin session (any slug allowed) OR a portal session whose `slug`
    matches the route's slug parameter.

    Used on per-client endpoints that should be writable both by the
    operator (admin-ui) and the client themselves (cal.diy iframe).

    Returns whichever identity authenticated, as a tagged union of the
    form `("admin", AdminSession)` or `("portal", PortalIdentity)` —
    callers can log which side made the change.
    """
    def _dep(request: Request) -> tuple[str, AdminSession | PortalIdentity]:
        settings = request.app.state.settings
        # Try admin first (cookie OR bearer)
        raw = _extract_token(request, settings.session_cookie_name)
        if raw:
            admin = verify_token(settings, raw)
            if admin is not None:
                return ("admin", admin)
            # An admin-shaped token that failed verify falls through to
            # portal attempt — they might be the same bearer header from
            # a portal page. Treating an invalid admin token as 'try
            # portal' is correct here.

        # Then portal (bearer only)
        bearer = _bearer_only(request)
        if bearer:
            portal = verify_portal_session(settings, bearer)
            if portal is not None:
                if portal.slug != slug:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"portal session is scoped to slug '{portal.slug}', cannot edit '{slug}'",
                    )
                return ("portal", portal)

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="admin or portal authentication required",
        )
    return _dep
