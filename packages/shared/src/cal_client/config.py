"""Env-driven config for cal_client.

Only one knob today (CAL_WEB_BASE). Kept as a separate module so future
packages (FastAPI receiver, Next.js fallback) can pull config without
importing the web-internals client.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    cal_web_base: str  # how WE connect to bookings@glnkco.com (e.g. http://localhost:3000 or http://host.docker.internal:3000)
    cal_public_base: str  # what URL goes into booking links shown to humans (e.g. http://localhost:3000)


def load_settings() -> Settings:
    base = os.environ.get("CAL_WEB_BASE", "http://localhost:3000").rstrip("/")
    public = os.environ.get("CAL_PUBLIC_BASE", base).rstrip("/")
    return Settings(cal_web_base=base, cal_public_base=public)
