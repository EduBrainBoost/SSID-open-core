"""Scores route — trust score queries. Hash-only identifiers."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()

_scores: dict[str, dict] = {}


@router.get("/")
async def list_scores(limit: int = 50):
    return {"count": len(_scores), "items": list(_scores.values())[:limit]}


@router.get("/{did_hash}")
async def get_score(did_hash: str):
    return _scores.get(did_hash, {"did_hash": did_hash, "score": 0, "factors": []})
