"""Policies route — policy listing and status."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()

_policies: list[dict] = []


@router.get("/")
async def list_policies():
    return {"count": len(_policies), "items": _policies}
