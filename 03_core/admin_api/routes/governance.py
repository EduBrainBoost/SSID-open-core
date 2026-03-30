"""Governance route — proposals and voting status."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_proposals():
    return {"count": 0, "items": []}
