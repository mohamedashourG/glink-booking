"""Local, gitignored, one-file-per-client store of provisioning records.

Each record contains the generated password and the cal.diy IDs we need for
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
