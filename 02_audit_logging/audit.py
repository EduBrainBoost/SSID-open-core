"""OpenCore public SDK — audit logging."""
from __future__ import annotations
import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class AuditEvent:
    """Public audit event schema."""

    def __init__(self, event_type: str, actor: str, target: str, result: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        self.event_type = event_type
        self.actor = actor
        self.target = target
        self.result = result
        self.metadata = metadata or {}
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.event_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        data = f"{self.event_type}:{self.actor}:{self.target}:{self.result}:{self.timestamp}"
        return hashlib.sha256(data.encode()).hexdigest()

    def to_dict(self) -> dict:
        return {
            "event_type": self.event_type,
            "actor": self.actor,
            "target": self.target,
            "result": self.result,
            "timestamp": self.timestamp,
            "event_hash": self.event_hash,
            "metadata": self.metadata,
        }


class AuditLog:
    """Public audit log — append-only, tamper-evident."""

    def __init__(self) -> None:
        self._events: List[AuditEvent] = []
        self._chain: List[str] = []

    def append(self, event: AuditEvent) -> None:
        prev_hash = self._chain[-1] if self._chain else "0" * 64
        chain_entry = hashlib.sha256(f"{event.event_hash}:{prev_hash}".encode()).hexdigest()
        self._events.append(event)
        self._chain.append(chain_entry)

    def verify_integrity(self) -> bool:
        """Verify the audit chain integrity."""
        if len(self._chain) != len(self._events):
            return False
        expected_prev = "0" * 64
        for event, expected_hash in zip(self._events, self._chain):
            actual_hash = hashlib.sha256(f"{event.event_hash}:{expected_prev}".encode()).hexdigest()
            if actual_hash != expected_hash:
                return False
            expected_prev = actual_hash
        return True

    def list_events(self, event_type: Optional[str] = None) -> List[dict]:
        if event_type is None:
            return [e.to_dict() for e in self._events]
        return [e.to_dict() for e in self._events if e.event_type == event_type]

    def chain_hash(self) -> str:
        return self._chain[-1] if self._chain else "0" * 64
