"""GET /clients (list) + GET /clients/{slug-or-email} (one)."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status

from admin_api.auth_dep import require_admin
from provisioning import store

router = APIRouter(prefix="/clients", tags=["clients"])


def _store_dir(request: Request) -> Path:
    return request.app.state.settings.store_dir


def _load_manifest(store_dir: Path) -> list[dict]:
    p = store_dir / store.MANIFEST_FILENAME
    if not p.exists():
        return []
    return json.loads(p.read_text())


def _has_webhook_coverage(store_dir: Path, *, client: dict) -> str:
    """One of: 'platform', 'per-user', 'none'."""
    plat = store_dir / "platform_webhook.json"
    if plat.exists():
        return "platform"
    # Fall back to per-user webhook id stored on the per-client record.
    rec = store.load(client.get("email", ""), store_dir=store_dir)
    if rec and rec.webhook_id:
        return "per-user"
    return "none"


@router.get("")
def list_clients(request: Request, _=Depends(require_admin)) -> dict:
    sdir = _store_dir(request)
    manifest = _load_manifest(sdir)
    items = []
    for c in manifest:
        items.append({
            "slug": c.get("slug"),
            "full_name": c.get("full_name"),
            "email": c.get("email"),
            "calendly_url": c.get("calendly_url"),
            "webhook_coverage": _has_webhook_coverage(sdir, client=c),
        })
    return {"clients": items}


@router.get("/{slug_or_email}")
def get_client(slug_or_email: str, request: Request, _=Depends(require_admin)) -> dict:
    sdir = _store_dir(request)
    manifest = _load_manifest(sdir)
    # Prefer email match (records are keyed by email).
    target_email = None
    for c in manifest:
        if c.get("email") == slug_or_email or c.get("slug") == slug_or_email:
            target_email = c.get("email")
            break
    if not target_email:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="client not found")
    rec = store.load(target_email, store_dir=sdir)
    if rec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="record file missing")
    return {
        "record": rec.to_dict(),
        "webhook_coverage": _has_webhook_coverage(sdir, client={"email": target_email}),
    }
