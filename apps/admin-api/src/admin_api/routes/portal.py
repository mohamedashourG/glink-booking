"""Endpoints for the iframe client portal.

Two endpoints, both unauthenticated (auth happens via the inbound JWT):

  POST /portal/exchange
       body: { "cal_token": "<jwt minted by cal.diy>" }
       200:  { "session": "...", "slug": "...", "expires_at": <epoch> }
       401:  invalid / expired token
       503:  feature disabled (PORTAL_JWT_SECRET not set)

  GET /portal/me
       Authorization: Bearer <portal-session-token>
       200:  { "slug": "...", "email": "...", "expires_at": <epoch> }
       401:  invalid / expired session

The iframe page calls /portal/exchange exactly once on mount, holds the
returned session token in memory, then uses it as Bearer for all
subsequent reads/writes (e.g. PUT /clients/<slug>/reminders).
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from admin_api import portal as portal_mod
from admin_api.auth_dep import require_portal_session

log = logging.getLogger(__name__)
router = APIRouter(prefix="/portal", tags=["portal"])


class ExchangeBody(BaseModel):
    cal_token: str


@router.post("/exchange")
def exchange(body: ExchangeBody, request: Request) -> dict:
    settings = request.app.state.settings
    try:
        identity = portal_mod.verify_cal_token(settings, body.cal_token)
    except portal_mod.PortalDisabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="portal disabled: PORTAL_JWT_SECRET not configured",
        )
    if identity is None:
        # Generic error message — don't leak which check failed.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or expired token",
        )
    session_token = portal_mod.issue_session(settings, identity)
    log.info("portal exchange: issued session for slug=%s (cal_token exp=%d)",
             identity.slug, identity.expires_at)
    return {
        "session": session_token,
        "slug": identity.slug,
        "email": identity.email,
        # exp of the *session*, not the original cal_token, so the iframe
        # knows when to ask the parent to re-mint.
        "expires_at": identity.expires_at + (
            request.app.state.settings.portal_session_ttl_seconds - 0
        ),
    }


@router.get("/me")
def me(request: Request) -> dict:
    """Diagnostic ping — confirms the session is still valid + which slug
    it's scoped to. Iframe uses this to know whether to re-handshake."""
    identity = require_portal_session(request)
    return {"slug": identity.slug, "email": identity.email, "expires_at": identity.expires_at}
