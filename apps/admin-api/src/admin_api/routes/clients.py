"""GET /clients (list) + GET /clients/{slug-or-email} (one).

Both endpoints augment the manifest-derived view with **live** data when
the optional Postgres pools are configured:

- live_username: pulled from cal.diy's `users.username`. If a client
  edited their slug in the cal.diy UI, that change shows up here without
  re-provisioning. When stored slug != live username, the response carries
  `drift = true` so the UI can flag it.
- bookings: from the receiver's `bookings` table. The list response gets
  per-client aggregate counts; the detail response gets the full row list.

Both live pieces degrade gracefully when their pool is absent — the
manifest-only view is still served. See `admin_api.databases` for the
contract.

Side effect on list: when drift is detected, the stored per-client record
is rewritten in place so the slug matches cal.diy. This is best-effort —
failures are logged and never block the response. After at least one
rewrite, clients.json is regenerated so the fallback site and other
manifest consumers see the new slug too.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status

from admin_api import bookings as bookings_mod
from admin_api import cal_live
from admin_api import reminders as reminders_mod
from admin_api.auth_dep import require_admin
from provisioning import store

log = logging.getLogger(__name__)

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


def _public_base() -> str:
    """Where booking links are addressed to. Mirrors cal_client.config so
    the link we rebuild matches what the provisioning code originally wrote."""
    base = os.environ.get("CAL_WEB_BASE", "http://localhost:3000").rstrip("/")
    return os.environ.get("CAL_PUBLIC_BASE", base).rstrip("/")


def _sync_drift_to_disk(store_dir: Path, email: str, live_username: str) -> bool:
    """Rewrite a per-client record so its slug + booking_link match cal.diy.

    Returns True if the record was updated, False if there was nothing to do
    or anything went wrong. Errors are logged but never raised — auto-sync
    must not block the dashboard rendering.
    """
    try:
        rec = store.load(email, store_dir=store_dir)
        if rec is None:
            return False
        # Idempotency guard. Caller already verified drift, but re-checking
        # here means concurrent requests writing the same fix don't both
        # bother — and protects against a stale `live_username` value.
        if (rec.slug or "").lower() == live_username.lower():
            return False
        new_link = f"{_public_base()}/{live_username}/{rec.event_type_slug}"
        log.info(
            "auto-sync: rewriting %s slug %r -> %r (booking_link -> %s)",
            email, rec.slug, live_username, new_link,
        )
        rec.slug = live_username
        rec.booking_link = new_link
        store.save(rec, store_dir=store_dir)
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("auto-sync: failed for %s: %s", email, exc)
        return False


@router.get("")
def list_clients(request: Request, _=Depends(require_admin)) -> dict:
    sdir = _store_dir(request)
    manifest = _load_manifest(sdir)

    cal_pool = getattr(request.app.state, "cal_pool", None)
    receiver_pool = getattr(request.app.state, "receiver_pool", None)

    # One round-trip each, then index by lowercased email + slug.
    usernames_by_email = cal_live.list_usernames(cal_pool)         # email_lc → username
    counts_by_slug = bookings_mod.counts_per_client(receiver_pool) # slug → ClientCounts

    # Pass 1: build the response rows. Track which records need their
    # stored slug rewritten to match cal.diy. We don't write inside the
    # loop so a write failure can't leave the response half-populated.
    items: list[dict] = []
    drifted_to_sync: list[tuple[str, str]] = []  # (email, live_username)
    for c in manifest:
        email_lc = (c.get("email") or "").lower()
        stored_slug = c.get("slug")
        live_username = usernames_by_email.get(email_lc)
        drift = bool(live_username and stored_slug and live_username.lower() != stored_slug.lower())
        if drift and c.get("email"):
            drifted_to_sync.append((c["email"], live_username))  # type: ignore[arg-type]

        # When we have a live username, that becomes the canonical slug
        # for booking-link rendering; the stored slug stays available so
        # the UI can show "was X, now Y".
        effective_slug = live_username or stored_slug

        # Booking counts are looked up by the slug the receiver saw, which
        # for drifted clients may be either old or new. Try both, prefer
        # whichever has data (drift cutover lands at the time of the
        # rename in cal.diy; bookings before and after may live under
        # different slugs).
        counts = bookings_mod._ZERO
        for s in (stored_slug, live_username):
            if not s:
                continue
            if s in counts_by_slug:
                counts = counts_by_slug[s]
                break

        items.append({
            "slug": stored_slug,
            "live_username": live_username,        # may be None when pool absent
            "effective_slug": effective_slug,       # what booking links should use
            "drift": drift,                         # stored != live
            "full_name": c.get("full_name"),
            "email": c.get("email"),
            "calendly_url": c.get("calendly_url"),
            "webhook_coverage": _has_webhook_coverage(sdir, client=c),
            "meetings": counts.to_dict(),
        })

    # Pass 2: best-effort auto-sync. Each write is independent — one
    # failure doesn't stop the others. If any record was updated, refresh
    # clients.json so the manifest (consumed by the fallback site, future
    # /clients calls, etc) matches the freshly-written records.
    synced_any = False
    for email, live in drifted_to_sync:
        if _sync_drift_to_disk(sdir, email, live):
            synced_any = True
    if synced_any:
        try:
            store.write_manifest(store_dir=sdir)
        except Exception as exc:  # noqa: BLE001
            log.warning("auto-sync: manifest refresh failed: %s", exc)

    # Reminder roll-ups for the dashboard. Two numbers: pending-in-24h
    # (the "do I need to worry" stat) and the full breakdown (used by
    # the per-status card if/when the UI shows it).
    rem_pending_24h = reminders_mod.pending_in_window(receiver_pool, window_hours=24)
    rem_agg = reminders_mod.aggregate_status(receiver_pool)

    # Convenience aggregate so the dashboard's stat card doesn't recompute.
    # `clients_with_drift` is computed on the pre-sync view so the operator
    # sees what was detected this load; it'll be 0 next refresh once the
    # write lands.
    totals = {
        "meetings_total":   sum(it["meetings"]["total"]       for it in items),
        "meetings_created": sum(it["meetings"]["created"]     for it in items),
        "meetings_rescheduled": sum(it["meetings"]["rescheduled"] for it in items),
        "meetings_cancelled":   sum(it["meetings"]["cancelled"]   for it in items),
        "meetings_rejected":    sum(it["meetings"]["rejected"]    for it in items),
        "clients_with_drift":   sum(1 for it in items if it["drift"]),
        "reminders_pending_24h": rem_pending_24h,
        "reminders_by_status":   rem_agg,
    }
    return {"clients": items, "totals": totals}


@router.get("/{slug_or_email}")
def get_client(slug_or_email: str, request: Request, _=Depends(require_admin)) -> dict:
    sdir = _store_dir(request)
    manifest = _load_manifest(sdir)

    target_email = None
    target = None
    for c in manifest:
        if c.get("email") == slug_or_email or c.get("slug") == slug_or_email:
            target = c
            target_email = c.get("email")
            break
    if not target_email or not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="client not found")

    rec = store.load(target_email, store_dir=sdir)
    if rec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="record file missing")

    cal_pool = getattr(request.app.state, "cal_pool", None)
    receiver_pool = getattr(request.app.state, "receiver_pool", None)

    usernames_by_email = cal_live.list_usernames(cal_pool)
    live_username = usernames_by_email.get(target_email.lower())
    drift = bool(live_username and live_username.lower() != (rec.slug or "").lower())
    effective_slug = live_username or rec.slug

    # Pull bookings under BOTH slugs (stored + live) and merge — covers
    # the rename cutover where some rows are under the old slug.
    seen_uids: set[str] = set()
    booking_list: list[dict] = []
    for s in {rec.slug, live_username} - {None}:
        for row in bookings_mod.list_for_client(receiver_pool, s):
            if row.cal_booking_uid in seen_uids:
                continue
            seen_uids.add(row.cal_booking_uid)
            booking_list.append(row.to_dict())

    counts = bookings_mod.counts_for_slug(receiver_pool, rec.slug)
    # If stored slug had no rows but live did, use live's counts.
    if counts.total == 0 and live_username:
        counts = bookings_mod.counts_for_slug(receiver_pool, live_username)

    # Reminder config + per-booking status. Config is resolved against
    # the *effective* slug — same one the receiver would use when a new
    # booking lands for this client.
    reminder_cfg = reminders_mod.get_config(receiver_pool, effective_slug or rec.slug)
    per_uid = reminders_mod.counts_per_uid(receiver_pool, effective_slug or rec.slug)
    if not per_uid and live_username and live_username != rec.slug:
        # Same drift handling as bookings — try the old slug too.
        per_uid = reminders_mod.counts_per_uid(receiver_pool, rec.slug)
    # Attach reminder counts onto each booking row in the response so the
    # UI doesn't need a second indexed lookup.
    for b in booking_list:
        b["reminders"] = per_uid.get(b["cal_booking_uid"], {
            "pending": 0, "processing": 0, "sent": 0, "failed": 0, "cancelled": 0,
        })

    return {
        "record": rec.to_dict(),
        "live_username": live_username,
        "effective_slug": effective_slug,
        "drift": drift,
        "webhook_coverage": _has_webhook_coverage(sdir, client={"email": target_email}),
        "meetings": counts.to_dict(),
        "bookings": booking_list,
        "reminder_config": reminder_cfg.to_dict(),
    }
