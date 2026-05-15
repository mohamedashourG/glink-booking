"""POST /auth/login, POST /auth/logout, GET /auth/me."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr

from admin_api.auth_dep import require_admin
from admin_api.cal_admin import authenticate_admin
from admin_api.session import AdminSession, issue_token

log = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginBody(BaseModel):
    email: EmailStr
    password: str


@router.post("/login")
def login(body: LoginBody, request: Request, response: Response) -> dict:
    settings = request.app.state.settings
    user = authenticate_admin(settings.cal_web_base, email=body.email, password=body.password)
    if user is None:
        # Single generic message — never leak whether it was bad creds vs not-admin.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials or not authorized",
        )
    token = issue_token(settings, email=user.email, role=user.role)
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        domain=settings.cookie_domain,
        path="/",
    )
    log.info("admin login OK: %s (role=%s)", user.email, user.role)
    # Return the token in the body too so the admin-ui can set its own
    # HTTP-only cookie on its own origin (Next.js server actions can't read
    # cookies set by another origin's response, even if same-site).
    return {
        "email": user.email,
        "role": user.role,
        "name": user.name,
        "inactive_admin_reason": user.inactive_admin_reason,
        "token": token,
        "expires_at": __import__("time").time() + settings.session_ttl_seconds,
    }


@router.post("/logout")
def logout(request: Request, response: Response) -> dict:
    settings = request.app.state.settings
    response.delete_cookie(
        key=settings.session_cookie_name,
        domain=settings.cookie_domain,
        path="/",
    )
    return {"ok": True}


@router.get("/me")
def me(session: AdminSession = Depends(require_admin)) -> dict:
    return {"email": session.email, "role": session.role, "expires_at": session.expires_at}
