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
    # Read-only Postgres connection strings for "live data" features.
    # Optional: when unset, /clients still works against the manifest but
    # without live usernames or booking counts. Set both for full features.
    cal_db_url: str | None        # cal.diy (glnk_booking) — for live usernames
    receiver_db_url: str | None   # receiver (glnk_receiver) — for bookings
    # Shared HMAC secret used to verify portal JWTs minted by cal.diy
    # (Path B / iframe client portal). When unset, the /portal/exchange
    # endpoint returns 503 — the rest of admin-api still works.
    portal_jwt_secret: str | None
    portal_session_ttl_seconds: int  # how long the exchanged session is good for


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
        cal_db_url=os.environ.get("CAL_DB_URL") or None,
        receiver_db_url=os.environ.get("RECEIVER_DB_URL") or None,
        portal_jwt_secret=os.environ.get("PORTAL_JWT_SECRET") or None,
        portal_session_ttl_seconds=int(os.environ.get("PORTAL_SESSION_TTL_SECONDS", "1800")),  # 30 min
    )
