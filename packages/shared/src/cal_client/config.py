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
    cal_web_base: str  # e.g. http://localhost:3000


def load_settings() -> Settings:
    base = os.environ.get("CAL_WEB_BASE", "http://localhost:3000").rstrip("/")
    return Settings(cal_web_base=base)
