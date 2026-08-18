"""OpenCore public SDK — synthetic datasets."""
from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone


class SyntheticDataset:
    """Base class for public synthetic datasets."""

    def __init__(self, name: str, license_: str, source: str) -> None:
        self.name = name
        self.license = license_
        self.source = source
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.pii = False

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "license": self.license,
            "source": self.source,
            "created_at": self.created_at,
            "pii": self.pii,
            "sha256": self._compute_hash(),
        }

    def _compute_hash(self) -> str:
        import hashlib
        content = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]


class IdentityFixtureDataset(SyntheticDataset):
    """Synthetic identity fixtures for testing."""

    def __init__(self) -> None:
        super().__init__(
            name="identity_synthetic_fixtures",
            license_="MIT",
            source="generated",
        )

    def records(self) -> list:
        return [
            {
                "did": "did:example:synthetic001",
                "name": "Synthetic User 001",
                "score": 0.75,
                "verification_status": "verified",
            },
            {
                "did": "did:example:synthetic002",
                "name": "Synthetic User 002",
                "score": 0.92,
                "verification_status": "pending",
            },
        ]


class PerformanceDataset(SyntheticDataset):
    """Synthetic performance data for benchmarking."""

    def __init__(self) -> None:
        super().__init__(
            name="performance_synthetic_benchmarks",
            license_="MIT",
            source="generated",
        )

    def records(self) -> list:
        return [
            {"metric": "latency_ms", "value": 12.5, "p99": 45.2},
            {"metric": "throughput_ops", "value": 1500.0, "p99": 2200.0},
            {"metric": "error_rate", "value": 0.001, "p99": 0.005},
        ]
