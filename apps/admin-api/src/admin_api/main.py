"""FastAPI app for admin-api: cal.diy admin-auth + provisioning over HTTP."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from admin_api.config import load_settings
from admin_api.routes import auth as auth_routes
from admin_api.routes import clients as clients_routes
from admin_api.routes import provision as provision_routes

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings()
    app.state.settings = settings
    log.info(
        "admin-api started — cal_web_base=%s store_dir=%s ui_origin=%s",
        settings.cal_web_base, settings.store_dir, settings.cors_allow_origin,
    )
    yield


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
app.include_router(provision_routes.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
