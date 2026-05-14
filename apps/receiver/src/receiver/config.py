"""Env-driven config for the receiver."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    webhook_secret: str


def load_settings() -> Settings:
    db = os.environ.get("DATABASE_URL")
    secret = os.environ.get("CAL_WEBHOOK_SECRET")
    missing = [name for name, val in (("DATABASE_URL", db), ("CAL_WEBHOOK_SECRET", secret)) if not val]
    if missing:
        raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")
    return Settings(database_url=db, webhook_secret=secret)  # type: ignore[arg-type]
