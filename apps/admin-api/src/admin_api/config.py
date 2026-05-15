"""Env-driven config for admin-api."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    cal_web_base: str
    session_secret: str
    session_cookie_name: str
    session_ttl_seconds: int
    cors_allow_origin: str
    store_dir: Path
    cookie_domain: str | None
    cookie_secure: bool


def load_settings() -> Settings:
    secret = os.environ.get("ADMIN_SESSION_SECRET")
    if not secret or len(secret) < 32:
        raise RuntimeError("ADMIN_SESSION_SECRET must be set and at least 32 chars")
    return Settings(
        cal_web_base=os.environ.get("CAL_WEB_BASE", "http://localhost:3000").rstrip("/"),
        session_secret=secret,
        session_cookie_name=os.environ.get("ADMIN_SESSION_COOKIE", "glink_admin_session"),
        session_ttl_seconds=int(os.environ.get("ADMIN_SESSION_TTL_SECONDS", "86400")),  # 24h
        cors_allow_origin=os.environ.get("ADMIN_UI_ORIGIN", "http://localhost:3001"),
        store_dir=Path(os.environ.get("STORE_DIR", "/app/.data")),
        cookie_domain=os.environ.get("ADMIN_COOKIE_DOMAIN") or None,
        cookie_secure=os.environ.get("ADMIN_COOKIE_SECURE", "false").lower() == "true",
    )
