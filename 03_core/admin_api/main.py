"""SSID Admin API — FastAPI application.

No PII storage. Non-custodial. Hash-only identifiers.
All mutations logged via audit middleware.
"""

from __future__ import annotations

import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="SSID Admin API",
    version="0.1.0",
    description="Admin Dashboard backend — non-custodial, hash-only, audit-logged",
)

_start_time = time.time()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3100"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

# --- Health endpoint ---

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "0.1.0",
        "uptime_seconds": round(time.time() - _start_time, 1),
    }


# --- Router registration ---

def _try_import(module_path: str, attr: str = "router"):
    try:
        mod = __import__(module_path, fromlist=[attr])
        return getattr(mod, attr), True
    except Exception:
        return None, False


_ROUTES = {
    "identities": "03_core.admin_api.routes.identities",
    "scores": "03_core.admin_api.routes.scores",
    "policies": "03_core.admin_api.routes.policies",
    "incidents": "03_core.admin_api.routes.incidents",
    "certificates": "03_core.admin_api.routes.certificates",
    "governance": "03_core.admin_api.routes.governance",
    "settings": "03_core.admin_api.routes.settings",
}

# Note: Python cannot import modules starting with digits directly.
# Use sys.path manipulation or run from repo root with PYTHONPATH set.
import sys
import os

_repo_root = os.environ.get("SSID_REPO", os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

for name, mod_path in _ROUTES.items():
    r, ok = _try_import(mod_path)
    if ok and r is not None:
        app.include_router(r, prefix=f"/api/{name}", tags=[name])

# Audit middleware (optional, fail-open for dev)
try:
    from importlib import import_module
    _audit_mod = import_module("03_core.admin_api.middleware.audit_mw")
    app.middleware("http")(_audit_mod.audit_middleware)
except Exception:
    pass
