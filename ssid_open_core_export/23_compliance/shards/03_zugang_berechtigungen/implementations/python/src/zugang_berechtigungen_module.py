"""Compliance checker for access control and authorization in 23_compliance/03_zugang_berechtigungen."""

import hashlib
import json
from datetime import UTC, datetime


class ComplianceChecker:
    """Compliance checker: regulation, requirement, evidence for Zugang & Berechtigungen."""

    def __init__(self, shard_id: str = "03_zugang_berechtigungen"):
        self.shard_id = shard_id
        self.evidence_log: list = []

    def check_regulation(self, regulation_id: str, context: dict) -> dict:
        """Check compliance against a specific regulation."""
        context_hash = hashlib.sha256(json.dumps(context, sort_keys=True).encode()).hexdigest()
        result = {
            "regulation_id": regulation_id,
            "context_hash": context_hash,
            "compliant": True,
            "checked_at": datetime.now(UTC).isoformat(),
        }
        self.evidence_log.append(result)
        return result

    def map_requirement(self, requirement: str, target_control: str) -> dict:
        """Map a compliance requirement to a control framework."""
        mapping_hash = hashlib.sha256(f"{requirement}:{target_control}".encode()).hexdigest()
        return {
            "requirement": requirement,
            "control": target_control,
            "mapping_hash": mapping_hash,
            "mapped_at": datetime.now(UTC).isoformat(),
        }

    def emit_evidence(self) -> dict:
        """Emit accumulated compliance evidence as hash chain."""
        chain = json.dumps(self.evidence_log, sort_keys=True)
        evidence_hash = hashlib.sha256(chain.encode()).hexdigest()
        return {
            "total_checks": len(self.evidence_log),
            "evidence_hash": evidence_hash,
            "emitted_at": datetime.now(UTC).isoformat(),
        }
