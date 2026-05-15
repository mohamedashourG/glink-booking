"""FastAPI dependency: pull + verify the session token on every protected route.

Accepts the token from either the session cookie (direct browser / curl use)
OR an `Authorization: Bearer <token>` header (the admin-ui's server-side
fetch path — see apps/admin-ui).
"""
from __future__ import annotations

from fastapi import HTTPException, Request, status

from admin_api.session import AdminSession, verify_token


def _extract_token(request: Request, cookie_name: str) -> str | None:
    auth = request.headers.get("Authorization") or request.headers.get("authorization")
    if auth and auth.lower().startswith("bearer "):
        return auth[7:].strip() or None
    return request.cookies.get(cookie_name)


def require_admin(request: Request) -> AdminSession:
    settings = request.app.state.settings
    raw = _extract_token(request, settings.session_cookie_name)
    if not raw:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not authenticated")
    session = verify_token(settings, raw)
    if session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or expired session")
    return session
