"""Admin-side helpers run OUTSIDE the per-client provisioning loop.

Today the only thing in here is the one-time platform-webhook bootstrap —
the single global webhook that fires for every cal.diy booking across
every client. Provisioning no longer registers per-user webhooks; instead
this command is run once after the cal.diy instance is stood up.

Admin credentials come from env: CAL_ADMIN_EMAIL + CAL_ADMIN_PASSWORD.
The admin must already exist in cal.diy (it's the system-admin user
created during the cal.diy setup wizard).

Idempotency note: cal.diy's `webhook.list` tRPC route returns `[]` for
admins even when platform webhooks exist (verified live). So we can't
"list, match by URL, skip if exists" the way we do for per-user webhooks.
Instead we record the platform webhook id in a local state file under
`.data/platform_webhook.json` after creating it, and re-runs short-
circuit on that. Side effect: if the webhook is deleted in cal.diy out
of band, the local file thinks it still exists — the runbook documents
how to recover (delete the local file, re-run).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from cal_client.cal_web import (
    CalWebError,
    CalWebSession,
    create_platform_webhook,
    login,
)

from provisioning import store


PLATFORM_WEBHOOK_STATE_FILENAME = "platform_webhook.json"


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


def _state_path(store_dir: Path | None = None) -> Path:
    return (store_dir or store.default_store_dir()) / PLATFORM_WEBHOOK_STATE_FILENAME


def _read_state(store_dir: Path | None = None) -> dict | None:
    p = _state_path(store_dir)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def _write_state(data: dict, store_dir: Path | None = None) -> Path:
    base = store_dir or store.default_store_dir()
    base.mkdir(parents=True, exist_ok=True)
    path = base / PLATFORM_WEBHOOK_STATE_FILENAME
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    path.chmod(0o600)
    return path


def bootstrap_platform_webhook(
    *,
    cal_web_base: str,
    admin: AdminCreds,
    subscriber_url: str,
    shared_secret: str,
    store_dir: Path | None = None,
) -> tuple[str, bool]:
    """Idempotently ensure the platform webhook exists. Returns `(id, created)`.

    Idempotency lives in `.data/platform_webhook.json`. If a state record
    matches the current `subscriber_url`, we trust it and return without
    calling cal.diy. If the URL changed (or there's no state), we create
    a fresh platform webhook and persist its id.
    """
    existing = _read_state(store_dir)
    if existing and existing.get("subscriber_url") == subscriber_url and existing.get("webhook_id"):
        return str(existing["webhook_id"]), False

    session: CalWebSession
    try:
        session = login(cal_web_base, email=admin.email, password=admin.password)
    except CalWebError as exc:
        raise SystemExit(f"admin login failed for {admin.email}: {exc}") from exc

    with session:
        webhook_id = create_platform_webhook(
            session,
            subscriber_url=subscriber_url,
            secret=shared_secret,
        )

    _write_state(
        {
            "webhook_id": webhook_id,
            "subscriber_url": subscriber_url,
            "admin_email": admin.email,
        },
        store_dir,
    )
    return webhook_id, True
