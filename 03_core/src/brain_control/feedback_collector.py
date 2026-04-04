"""Structured feedback collector."""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path


class FeedbackCollector:
    def __init__(self, store_dir: Path):
        self.dir = Path(store_dir)
        self.dir.mkdir(parents=True, exist_ok=True)

    def collect(
        self, session_id: str, interaction_id: str, rating: int, comment: str = "", metadata: dict | None = None
    ) -> str:
        fb_id = f"fb_{uuid.uuid4().hex[:12]}"
        entry = {
            "feedback_id": fb_id,
            "session_id": session_id,
            "interaction_id": interaction_id,
            "rating": max(1, min(5, rating)),
            "comment": comment,
            "metadata": metadata or {},
            "timestamp": time.time(),
        }
        (self.dir / f"{fb_id}.json").write_text(json.dumps(entry, indent=2, ensure_ascii=False), encoding="utf-8")
        return fb_id

    def export(self, min_rating: int = 1) -> list[dict]:
        results = []
        for f in self.dir.glob("fb_*.json"):
            fb = json.loads(f.read_text(encoding="utf-8"))
            if fb.get("rating", 0) >= min_rating:
                results.append(fb)
        return sorted(results, key=lambda x: x.get("timestamp", 0))
