"""OpenCore public SDK — observability score interface."""
from __future__ import annotations
import hashlib
from datetime import datetime, timezone


class ScoreEngine:
    """Public score computation engine."""

    def __init__(self) -> None:
        self._scores: dict[str, dict] = {}

    def compute_score(self, module: str, criteria: dict) -> dict:
        """Compute a public compliance score."""
        score_data = {
            "module": module,
            "criteria": criteria,
            "computed_at": datetime.now(timezone.utc).isoformat(),
            "score": self._calculate_score(criteria),
            "grade": self._assign_grade(self._calculate_score(criteria)),
        }
        self._scores[module] = score_data
        return score_data

    def _calculate_score(self, criteria: dict) -> float:
        """Calculate composite score from criteria weights."""
        if not criteria:
            return 0.0
        total = sum(v * w for w, v in criteria.items())
        max_score = sum(criteria.values())
        return round((total / max_score) * 100, 2) if max_score > 0 else 0.0

    def _assign_grade(self, score: float) -> str:
        if score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        return "F"

    def get_score(self, module: str) -> dict | None:
        return self._scores.get(module)

    def list_scores(self) -> list:
        return list(self._scores.values())

    def generate_hashchain_entry(self, module: str, prev_hash: str = "0" * 64) -> dict:
        """Generate a tamper-evident hashchain entry."""
        data = f"{module}:{prev_hash}:{datetime.now(timezone.utc).isoformat()}"
        event_hash = hashlib.sha256(data.encode()).hexdigest()
        return {
            "module": module,
            "prev_hash": prev_hash,
            "event_hash": event_hash,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
