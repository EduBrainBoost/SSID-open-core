"""Certificates route — certificate listing."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_certificates():
    return {"count": 0, "items": []}
