"""Local, gitignored, one-file-per-client store of provisioning records.

Each record contains the generated password and the bookings@glnkco.com IDs we need for
idempotent re-runs. The directory is gitignored; treat its contents as
secrets.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from cal_client import ProvisionedClient


def default_store_dir() -> Path:
    # Repo-root/.data — anchored from this package's install location is
    # awkward, so prefer CWD/.data for a CLI run from the repo.
    return Path.cwd() / ".data"


_SAFE = re.compile(r"[^a-z0-9._-]+")


def _record_filename(email: str) -> str:
    return _SAFE.sub("_", email.lower()) + ".json"


def record_path(email: str, store_dir: Path | None = None) -> Path:
    return (store_dir or default_store_dir()) / _record_filename(email)


def load(email: str, store_dir: Path | None = None) -> ProvisionedClient | None:
    path = record_path(email, store_dir)
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    return ProvisionedClient(**data)


def save(record: ProvisionedClient, store_dir: Path | None = None) -> Path:
    base = store_dir or default_store_dir()
    base.mkdir(parents=True, exist_ok=True)
    path = base / _record_filename(record.email)
    path.write_text(json.dumps(record.to_dict(), indent=2, sort_keys=True))
    path.chmod(0o600)
    return path


# --- public manifest -------------------------------------------------------
# clients.json sits alongside the per-client records but is the safe-to-read
# subset (no passwords, no internal IDs) — slug / full_name / email /
# calendly_url. It's the static source of truth the outage-fallback Next.js
# app (apps/fallback/) reads at BUILD time. Regenerated on every provisioning
# run by walking the store dir.

MANIFEST_FILENAME = "clients.json"


def manifest_path(store_dir: Path | None = None) -> Path:
    return (store_dir or default_store_dir()) / MANIFEST_FILENAME


def write_manifest(store_dir: Path | None = None) -> Path:
    """(Re)build clients.json from every per-client record in the store dir.

    Idempotent — re-running provisioning rebuilds it from current state, so
    additions/updates flow through without bookkeeping. Safe to commit *only*
    if you really want clients listed publicly; .gitignore covers .data/ by
    default to keep both this file and the per-client records private.
    """
    base = store_dir or default_store_dir()
    base.mkdir(parents=True, exist_ok=True)
    entries: list[dict] = []
    for child in sorted(base.glob("*.json")):
        if child.name == MANIFEST_FILENAME:
            continue
        # Skip dotfiles — macOS AppleDouble sidecars (`._foo.json`) match
        # `*.json` but are binary metadata, not records. Reading them as
        # text raises UnicodeDecodeError.
        if child.name.startswith("."):
            continue
        try:
            data = json.loads(child.read_text())
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        # Skip non-record .json files in the store (e.g. platform_webhook.json),
        # which match the glob but don't carry per-client fields.
        if not isinstance(data, dict) or not data.get("slug"):
            continue
        entries.append(
            {
                "slug": data.get("slug"),
                "full_name": data.get("full_name"),
                "email": data.get("email"),
                "calendly_url": data.get("calendly_url"),
            }
        )
    out = base / MANIFEST_FILENAME
    out.write_text(json.dumps(entries, indent=2, sort_keys=True) + "\n")
    out.chmod(0o644)
    return out
