"""GET /slug-available?slug=<s> — live check against cal.diy + local manifest.

Used by the new-client form for inline pre-submit validation. The form
already does a local-manifest check (so it warns even when admin-api is
disconnected), but that check is blind to cal.diy users provisioned out
of band (e.g. signed up directly through the cal.diy UI). This endpoint
covers that gap.

The endpoint deliberately does NOT 4xx on a taken slug. It returns 200
with a JSON body the client uses to render guidance — keeps the
distinction between "taken" and "request failed" crisp in the UI.
"""
from __future__ import annotations

import json
import re

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from admin_api import cal_live
from admin_api.auth_dep import require_admin
from provisioning import store

router = APIRouter(tags=["slug"])

# Same regex cal.com uses on usernames (alphanumeric, hyphen, underscore).
# We're stricter than cal.diy's own validator on purpose — keeping a
# narrower surface keeps URL/copy/paste predictable.
_VALID = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,38}[a-z0-9])?$")


def _local_slug_taken(store_dir, candidate: str) -> bool:
    """Manifest-only check. Cheap, doesn't touch cal.diy."""
    p = store_dir / store.MANIFEST_FILENAME
    if not p.exists():
        return False
    try:
        entries = json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return False
    needle = candidate.lower()
    return any(
        isinstance(e, dict) and (e.get("slug") or "").lower() == needle
        for e in entries
    )


@router.get("/slug-available")
def slug_available(
    request: Request,
    slug: str = Query(min_length=1, max_length=40),
    _=Depends(require_admin),
) -> dict:
    """Returns the combined check.

    Response shape:
        {
          "slug": "<normalized>",
          "valid_format": bool,                    # passes the regex
          "taken_in_manifest": bool,               # already provisioned by us
          "taken_in_cal":      bool | null,        # live check; null = couldn't check
          "available":         bool,               # convenience: format ok AND
                                                   # not taken in either place
                                                   # (errs toward 'unavailable'
                                                   # when cal.diy check fails)
        }
    """
    normalized = slug.strip().lower()
    valid_format = bool(_VALID.match(normalized))
    if not valid_format:
        return {
            "slug": normalized,
            "valid_format": False,
            "taken_in_manifest": False,
            "taken_in_cal": None,
            "available": False,
        }

    sdir = request.app.state.settings.store_dir
    taken_local = _local_slug_taken(sdir, normalized)

    cal_pool = getattr(request.app.state, "cal_pool", None)
    taken_cal = cal_live.is_username_taken(cal_pool, normalized)

    # "available" is the safe boolean — if either source says taken (or
    # cal.diy check is broken), we treat it as not available. The full
    # tri-state is in the other fields for the UI to render nuance.
    available = (not taken_local) and (taken_cal is False)

    return {
        "slug": normalized,
        "valid_format": True,
        "taken_in_manifest": taken_local,
        "taken_in_cal": taken_cal,
        "available": available,
    }
