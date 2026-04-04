"""Identities route — list, get, update identity summaries. Hash-only, no PII."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()

# In-memory store (MVP — production uses persistent store)
_identities: dict[str, dict] = {}


@router.get("/")
async def list_identities(limit: int = 50, offset: int = 0):
    items = list(_identities.values())[offset : offset + limit]
    return {"count": len(_identities), "items": items}


@router.get("/{did_hash}")
async def get_identity(did_hash: str):
    entry = _identities.get(did_hash)
    if not entry:
        return {"error": "not_found"}, 404
    return entry
