"""Admin-side helpers run OUTSIDE the per-client provisioning loop.

Today the only thing in here is the one-time platform-webhook bootstrap —
the single global webhook that fires for every cal.diy booking across
every client. Provisioning no longer registers per-user webhooks; instead
this command is run once after the cal.diy instance is stood up.

Admin credentials come from env: CAL_ADMIN_EMAIL + CAL_ADMIN_PASSWORD.
The admin must already exist in cal.diy (it's the system-admin user
created during the cal.diy setup wizard).
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from cal_client.cal_web import (
    CalWebError,
    CalWebSession,
    ensure_platform_webhook,
    login,
)


@dataclass(frozen=True)
class AdminCreds:
    email: str
    password: str


def load_admin_creds() -> AdminCreds:
    email = os.environ.get("CAL_ADMIN_EMAIL")
    password = os.environ.get("CAL_ADMIN_PASSWORD")
    missing = [k for k, v in (("CAL_ADMIN_EMAIL", email), ("CAL_ADMIN_PASSWORD", password)) if not v]
    if missing:
        raise SystemExit(
            "bootstrap-webhook needs admin credentials. Missing: "
            + ", ".join(missing)
            + ". This is the cal.diy system-admin user (role=ADMIN), not a client."
        )
    return AdminCreds(email=email, password=password)  # type: ignore[arg-type]


def bootstrap_platform_webhook(
    *,
    cal_web_base: str,
    admin: AdminCreds,
    subscriber_url: str,
    shared_secret: str,
) -> tuple[str, bool]:
    """Log in as admin and idempotently ensure the platform webhook exists.

    Returns `(webhook_id, created)`; if the platform webhook for
    `subscriber_url` already exists, `created` is False and we just re-use
    its id. Safe to re-run.
    """
    session: CalWebSession
    try:
        session = login(cal_web_base, email=admin.email, password=admin.password)
    except CalWebError as exc:
        raise SystemExit(f"admin login failed for {admin.email}: {exc}") from exc
    with session:
        return ensure_platform_webhook(
            session,
            subscriber_url=subscriber_url,
            secret=shared_secret,
        )
