"""Settings route — system configuration (read-only for non-superadmin)."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def get_settings():
    return {"theme": "neon_civic", "locale": "de", "audit_enabled": True}
