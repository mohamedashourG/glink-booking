"""Signed-JWT session cookies.

Stateless: no server-side session store. The cookie is the session.
Validated on every request.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import jwt

from admin_api.cal_admin import ADMIN_ROLES
from admin_api.config import Settings


_ALG = "HS256"
_LEEWAY = 5  # seconds — small clock-skew tolerance


@dataclass(frozen=True)
class AdminSession:
    email: str
    role: str
    expires_at: int  # epoch seconds


def issue_token(settings: Settings, *, email: str, role: str) -> str:
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": email,
        "role": role,
        "iat": now,
        "exp": now + settings.session_ttl_seconds,
    }
    return jwt.encode(payload, settings.session_secret, algorithm=_ALG)


def verify_token(settings: Settings, token: str) -> AdminSession | None:
    try:
        payload = jwt.decode(
            token,
            settings.session_secret,
            algorithms=[_ALG],
            leeway=_LEEWAY,
            options={"require": ["exp", "sub", "role"]},
        )
    except jwt.PyJWTError:
        return None
    role = str(payload.get("role"))
    if role not in ADMIN_ROLES:
        # Cookie encodes a non-admin role — refuse, even if signature valid.
        return None
    return AdminSession(
        email=str(payload["sub"]),
        role=role,
        expires_at=int(payload["exp"]),
    )
