#!/usr/bin/env python3
"""
Write-Override Registry Management
Version: 1.0
Date: 2025-09-16

Manages write-override registry with expiration tracking and evidence generation.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

class WriteOverrideRegistry:
    def __init__(self, registry_path="23_compliance/evidence/write_override_registry.json"):
        self.registry_path = Path(registry_path)
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        self.registry = self._load_registry()

    def _load_registry(self):
        """Load existing registry or create new one"""
        if self.registry_path.exists():
            try:
                with open(self.registry_path, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

        return {
            "version": "1.0",
            "created": datetime.now().isoformat(),
            "overrides": [],
            "expired_count": 0,
            "active_count": 0
        }

    def _save_registry(self):
        """Save registry to disk"""
        self.registry["last_updated"] = datetime.now().isoformat()
        with open(self.registry_path, 'w') as f:
            json.dump(self.registry, f, indent=2)

    def expire_overrides(self, expire_hours=48):
        """Remove expired overrides"""
        now = datetime.now()
        cutoff = now - timedelta(hours=expire_hours)

        active_overrides = []
        expired_count = 0

        for override in self.registry.get("overrides", []):
            created = datetime.fromisoformat(override.get("created", "1970-01-01"))
            if created > cutoff:
                active_overrides.append(override)
            else:
                expired_count += 1

        self.registry["overrides"] = active_overrides
        self.registry["expired_count"] = expired_count
        self.registry["active_count"] = len(active_overrides)

        return expired_count

    def add_override(self, file_path, reason, author="system"):
        """Add new write override"""
        override = {
            "id": len(self.registry["overrides"]) + 1,
            "file_path": str(file_path),
            "reason": reason,
            "author": author,
            "created": datetime.now().isoformat(),
            "status": "active"
        }

        self.registry["overrides"].append(override)
        self.registry["active_count"] = len(self.registry["overrides"])

    def generate_evidence(self):
        """Generate evidence log"""
        evidence_dir = Path("23_compliance/evidence/ci_runs")
        evidence_dir.mkdir(parents=True, exist_ok=True)

        evidence_file = evidence_dir / f"write_override_evidence_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        evidence = {
            "timestamp": datetime.now().isoformat(),
            "registry_status": {
                "active_overrides": self.registry["active_count"],
                "expired_overrides": self.registry["expired_count"],
                "total_processed": len(self.registry["overrides"])
            },
            "compliance_score": 100 if self.registry["active_count"] == 0 else max(0, 100 - self.registry["active_count"] * 5),
            "evidence_type": "write_override_registry"
        }

        with open(evidence_file, 'w') as f:
            json.dump(evidence, f, indent=2)

        return evidence_file

def main():
    parser = argparse.ArgumentParser(description="Manage write-override registry")
    parser.add_argument("--expire", default="48h", help="Expiration time (e.g., 48h)")
    parser.add_argument("--evidence", action="store_true", help="Generate evidence log")
    parser.add_argument("--add-override", nargs=2, metavar=("FILE", "REASON"), help="Add override")

    args = parser.parse_args()

    registry = WriteOverrideRegistry()

    # Parse expiration time
    expire_hours = 48
    if args.expire.endswith('h'):
        expire_hours = int(args.expire[:-1])

    # Expire old overrides
    expired_count = registry.expire_overrides(expire_hours)
    print(f"Expired {expired_count} write overrides older than {expire_hours} hours")

    # Add new override if requested
    if args.add_override:
        file_path, reason = args.add_override
        registry.add_override(file_path, reason)
        print(f"Added write override for {file_path}")

    # Save registry
    registry._save_registry()

    # Generate evidence if requested
    if args.evidence:
        evidence_file = registry.generate_evidence()
        print(f"Evidence generated: {evidence_file}")
        print(f"Active overrides: {registry.registry['active_count']}")
        print(f"Registry status: {'COMPLIANT' if registry.registry['active_count'] == 0 else 'NON-COMPLIANT'}")

if __name__ == "__main__":
    main()