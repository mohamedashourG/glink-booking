"""POST /provision/single, POST /provision/batch (multipart CSV)."""
from __future__ import annotations

import csv
import io
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, EmailStr, Field

from admin_api.auth_dep import require_admin
from cal_client import Client, load_settings as load_cal_settings
from provisioning import store
from provisioning.provision import ProvisionError, provision_client

log = logging.getLogger(__name__)

router = APIRouter(prefix="/provision", tags=["provision"])


class SingleClientBody(BaseModel):
    full_name: str = Field(min_length=1)
    email: EmailStr
    slug: str = Field(min_length=1)
    timezone: str = "America/New_York"
    work_start: str = "09:00"
    work_end: str = "18:00"
    calendly_url: str | None = None


def _result(record_dict: dict, *, created: bool) -> dict:
    return {
        "ok": True,
        "created": created,
        "record": record_dict,
    }


def _provision_with_store(client: Client, store_dir: Path) -> dict:
    """Run the existing provisioning code, scoped to a specific store dir.

    `provision_client` reads/writes the store via store.default_store_dir(),
    which uses Path.cwd() / .data — so we chdir to the parent of store_dir
    for the duration of the call, then restore.
    """
    import os

    cal_settings = load_cal_settings()
    prev = Path.cwd()
    parent = store_dir.parent
    parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chdir(parent)
        result = provision_client(client, cal_settings)
    finally:
        os.chdir(prev)
    # Refresh the manifest each time so the dashboard list stays in sync.
    store.write_manifest(store_dir=store_dir)
    return _result(result.record.to_dict(), created=result.created)


@router.post("/single")
def provision_single(body: SingleClientBody, request: Request, _=Depends(require_admin)) -> dict:
    client = Client(
        full_name=body.full_name,
        email=body.email,
        slug=body.slug,
        timezone=body.timezone,
        work_start=body.work_start,
        work_end=body.work_end,
        calendly_url=body.calendly_url,
    )
    sdir = request.app.state.settings.store_dir
    try:
        return _provision_with_store(client, sdir)
    except ProvisionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"step": exc.step, "email": exc.email, "message": str(exc)},
        )


@router.post("/batch")
def provision_batch(
    request: Request,
    csv_file: UploadFile = File(..., alias="file"),
    _=Depends(require_admin),
) -> dict:
    raw = csv_file.file.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CSV must be UTF-8")

    reader = csv.DictReader(io.StringIO(text))
    required = {"full_name", "email", "slug"}
    missing = required - set(reader.fieldnames or [])
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"CSV missing required columns: {sorted(missing)}",
        )

    sdir = request.app.state.settings.store_dir
    rows: list[dict] = []
    for i, row in enumerate(reader, start=2):
        try:
            client = Client(
                full_name=(row.get("full_name") or "").strip(),
                email=(row.get("email") or "").strip(),
                slug=(row.get("slug") or "").strip(),
                timezone=(row.get("timezone") or "").strip() or "America/New_York",
                work_start=(row.get("work_start") or "").strip() or "09:00",
                work_end=(row.get("work_end") or "").strip() or "18:00",
                calendly_url=(row.get("calendly_url") or "").strip() or None,
            )
        except Exception as exc:  # row-level malformed input
            rows.append({"row": i, "ok": False, "step": "parse", "message": str(exc)})
            continue

        if not client.email or not client.slug or not client.full_name:
            rows.append(
                {"row": i, "ok": False, "step": "parse", "message": "missing full_name/email/slug"}
            )
            continue

        try:
            res = _provision_with_store(client, sdir)
            rows.append({
                "row": i,
                "ok": True,
                "email": client.email,
                "slug": client.slug,
                "created": res["created"],
                "record": res["record"],
            })
        except ProvisionError as exc:
            rows.append({
                "row": i,
                "ok": False,
                "email": exc.email,
                "step": exc.step,
                "message": str(exc),
            })

    return {"results": rows}
