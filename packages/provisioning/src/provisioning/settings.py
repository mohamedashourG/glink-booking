"""Provisioning-specific env vars (the wiring layer between cal.diy and the receiver).

These live here, not in `cal_client.config`, because they're about
*pointing cal.diy at the receiver* — not about talking to cal.diy.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class WebhookSettings:
    receiver_url: str   # e.g. http://host.docker.internal:8000/webhook
    shared_secret: str  # must match the value the receiver was started with


def load_webhook_settings() -> WebhookSettings:
    url = os.environ.get("RECEIVER_WEBHOOK_URL")
    secret = os.environ.get("CAL_WEBHOOK_SECRET")
    missing = [k for k, v in (("RECEIVER_WEBHOOK_URL", url), ("CAL_WEBHOOK_SECRET", secret)) if not v]
    if missing:
        raise SystemExit(
            "Missing required env vars: "
            + ", ".join(missing)
            + ". CAL_WEBHOOK_SECRET must match the receiver's CAL_WEBHOOK_SECRET."
        )
    return WebhookSettings(receiver_url=url, shared_secret=secret)  # type: ignore[arg-type]
