"""FastAPI app for admin-api: bookings@glnkco.com admin-auth + provisioning over HTTP."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from admin_api import databases
from admin_api.config import load_settings
from admin_api.routes import auth as auth_routes
from admin_api.routes import clients as clients_routes
from admin_api.routes import portal as portal_routes
from admin_api.routes import provision as provision_routes
from admin_api.routes import reminders as reminders_routes
from admin_api.routes import slug as slug_routes

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings()
    app.state.settings = settings
    # Optional read-only pools — see admin_api.databases for the contract.
    # Either or both may be None; routes degrade gracefully.
    app.state.cal_pool = databases.open_optional_pool("cal.diy", settings.cal_db_url)
    app.state.receiver_pool = databases.open_optional_pool("receiver", settings.receiver_db_url)
    log.info(
        "admin-api started — cal_web_base=%s store_dir=%s ui_origin=%s cal_db=%s receiver_db=%s",
        settings.cal_web_base, settings.store_dir, settings.cors_allow_origin,
        "on" if app.state.cal_pool else "off",
        "on" if app.state.receiver_pool else "off",
    )
    try:
        yield
    finally:
        databases.close_pool("cal.diy", app.state.cal_pool)
        databases.close_pool("receiver", app.state.receiver_pool)


app = FastAPI(lifespan=lifespan, title="glink-booking admin-api")

# Allow the admin-ui origin only. Credentials must be enabled so the
# session cookie rides cross-port (admin-ui:3001 → admin-api:8002, both
# on localhost = same-site for cookie purposes, so SameSite=Lax suffices).
import os as _os
_origins_env = _os.environ.get("ADMIN_UI_ORIGIN", "http://localhost:3001")
_origins = [o.strip() for o in _origins_env.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(auth_routes.router)
app.include_router(clients_routes.router)
app.include_router(portal_routes.router)
app.include_router(provision_routes.router)
app.include_router(reminders_routes.router)
app.include_router(slug_routes.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
