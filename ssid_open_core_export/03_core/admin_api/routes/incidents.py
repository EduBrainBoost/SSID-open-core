"""Incidents route — incident management."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()

_incidents: list[dict] = []


@router.get("/")
async def list_incidents():
    return {"count": len(_incidents), "items": _incidents}
