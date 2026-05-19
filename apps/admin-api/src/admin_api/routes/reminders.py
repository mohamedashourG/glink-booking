"""PUT /clients/{slug-or-email}/reminders — per-client reminder config.

The admin-ui's Reminders card sends:
    { "offsets_min": [60, 1440], "recipients": ["prospect", "host"] }

We resolve the target by slug *or* email (mirror of GET /clients/<x>),
validate/normalize, then UPSERT into receiver-DB.

Validation happens both here (pydantic, surfaces a 400 on bad input) AND
in the admin_api.reminders module (defensive normalization). Two layers
means the UI gets a fast, clear 400; the DB layer never trusts the route.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator

from admin_api import reminders as reminders_mod
from admin_api.auth_dep import require_admin_or_portal_for_slug
from provisioning import store

log = logging.getLogger(__name__)

router = APIRouter(prefix="/clients", tags=["reminders"])

_VALID_ROLES = {"prospect", "host", "agency"}


class ReminderConfigBody(BaseModel):
    # Bounds: 0 to 24h × 30d  = 43200 minutes. More than 30 days out and
    # we're in calendar-app territory; less than 1 minute is a typo.
    offsets_min: list[int] = Field(..., max_length=10)
    recipients: list[str] = Field(..., max_length=3)

    @field_validator("offsets_min")
    @classmethod
    def _offsets_ok(cls, v: list[int]) -> list[int]:
        for n in v:
            if n < 1 or n > 43200:
                raise ValueError(
                    f"offset {n} out of range; must be 1..43200 minutes (1 min to 30 days)"
                )
        return v

    @field_validator("recipients")
    @classmethod
    def _recipients_ok(cls, v: list[str]) -> list[str]:
        bad = [r for r in v if r.lower() not in _VALID_ROLES]
        if bad:
            raise ValueError(
                f"unknown recipient role(s): {bad}; must be subset of {sorted(_VALID_ROLES)}"
            )
        return v


def _resolve_slug(store_dir: Path, slug_or_email: str) -> str:
    """Look up the canonical slug for a slug-or-email path param.

    Required because admin-ui detail-page URLs use email *or* slug, but
    reminder rows are keyed by slug. We hit the manifest (cheap, in-memory
    after disk read) rather than parsing per-client JSON files.
    """
    p = store_dir / store.MANIFEST_FILENAME
    if not p.exists():
        raise HTTPException(status_code=404, detail="manifest empty; no clients yet")
    try:
        entries = json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        raise HTTPException(status_code=500, detail="manifest unreadable")
    for c in entries:
        if c.get("email") == slug_or_email or c.get("slug") == slug_or_email:
            slug = c.get("slug")
            if slug:
                return slug
    raise HTTPException(status_code=404, detail="client not found")


@router.put("/{slug_or_email}/reminders")
def put_reminders(
    slug_or_email: str,
    body: ReminderConfigBody,
    request: Request,
) -> dict:
    sdir = request.app.state.settings.store_dir
    slug = _resolve_slug(sdir, slug_or_email)

    # Auth: admin OR portal-session matching this slug. Resolved AFTER
    # path → slug so a portal session for "acme" can't edit "beta" via
    # path-param `acme@example.com` (the resolver normalizes to slug).
    kind, ident = require_admin_or_portal_for_slug(slug)(request)
    log.info("reminders PUT %s by %s (%s)", slug, kind,
             getattr(ident, "email", "?"))

    pool = getattr(request.app.state, "receiver_pool", None)
    if pool is None:
        # Without the pool the dashboard can degrade gracefully, but a
        # write must hard-fail — silently dropping the user's save is
        # worse than telling them to set RECEIVER_DB_URL.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="reminders disabled: RECEIVER_DB_URL not configured on admin-api",
        )

    try:
        cfg = reminders_mod.set_config(
            pool, slug,
            offsets_min=body.offsets_min,
            recipients=body.recipients,
        )
    except Exception as exc:  # noqa: BLE001
        log.exception("reminders PUT failed for %s", slug)
        raise HTTPException(status_code=500, detail=f"upsert failed: {exc}")

    return {"ok": True, "slug": slug, "config": cfg.to_dict(), "edited_by": kind}


@router.get("/{slug_or_email}/reminders")
def get_reminders(slug_or_email: str, request: Request) -> dict:
    """Read the current reminder config.

    Mirrors the auth rules of PUT — admin OR portal-for-this-slug — so
    the iframe can fetch its own row to pre-populate the editor without
    needing the full /clients/<slug> blob (which is admin-only and
    includes other people's data).
    """
    sdir = request.app.state.settings.store_dir
    slug = _resolve_slug(sdir, slug_or_email)
    require_admin_or_portal_for_slug(slug)(request)

    pool = getattr(request.app.state, "receiver_pool", None)
    cfg = reminders_mod.get_config(pool, slug)
    return {"slug": slug, "config": cfg.to_dict()}
