"""Orchestration coordinator for access control and authorization in 24_meta_orchestration/03_zugang_berechtigungen."""
import hashlib
import json
from datetime import datetime, timezone


class OrchestrationCoordinator:
    """Orchestration coordinator: dispatch, monitor, evidence for Zugang & Berechtigungen."""

    def __init__(self, shard_id: str = "03_zugang_berechtigungen"):
        self.shard_id = shard_id
        self.task_registry: dict = {}

    def dispatch(self, task_id: str, target_root: str, payload: dict) -> dict:
        """Dispatch task to target root (non-custodial, hash evidence)."""
        payload_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode()
        ).hexdigest()
        task = {
            "task_id": task_id,
            "target_root": target_root,
            "payload_hash": payload_hash,
            "status": "dispatched",
            "dispatched_at": datetime.now(timezone.utc).isoformat(),
        }
        self.task_registry[task_id] = task
        return task

    def monitor_status(self, task_id: str) -> dict:
        """Monitor task execution status."""
        task = self.task_registry.get(task_id)
        if not task:
            return {"error": "not_found", "task_id": task_id}
        return {
            "task_id": task_id,
            "status": task["status"],
            "monitored_at": datetime.now(timezone.utc).isoformat(),
        }

    def collect_evidence(self) -> dict:
        """Collect evidence from all dispatched tasks."""
        chain = json.dumps(list(self.task_registry.values()), sort_keys=True)
        evidence_hash = hashlib.sha256(chain.encode()).hexdigest()
        return {
            "total_tasks": len(self.task_registry),
            "evidence_hash": evidence_hash,
            "collected_at": datetime.now(timezone.utc).isoformat(),
        }
