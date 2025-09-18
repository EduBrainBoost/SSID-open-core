#!/usr/bin/env python3
"""
Evidence Registry Management
Version: 1.0
Date: 2025-09-16

Maintains central registry of all compliance evidence and audit logs.
"""

import argparse
import json
import os
from datetime import datetime
from pathlib import Path

class EvidenceRegistry:
    def __init__(self):
        self.registry_path = Path("23_compliance/evidence/evidence_registry.json")
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        self.registry = self._load_registry()

    def _load_registry(self):
        """Load existing registry or create new"""
        if self.registry_path.exists():
            try:
                with open(self.registry_path, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

        return {
            "version": "1.0",
            "created": datetime.now().isoformat(),
            "evidence_entries": [],
            "statistics": {
                "total_entries": 0,
                "compliance_checks": 0,
                "policy_reviews": 0,
                "structure_validations": 0
            }
        }

    def _save_registry(self):
        """Save registry to disk"""
        self.registry["last_updated"] = datetime.now().isoformat()
        with open(self.registry_path, 'w') as f:
            json.dump(self.registry, f, indent=2)

    def scan_and_register_evidence(self):
        """Scan evidence directory and register all evidence files"""
        evidence_dir = Path("23_compliance/evidence")
        new_entries = 0

        if not evidence_dir.exists():
            print("No evidence directory found")
            return 0

        # Find all evidence files
        evidence_files = list(evidence_dir.rglob("*_evidence_*.json"))
        evidence_files.extend(evidence_dir.rglob("*_log_*.json"))
        evidence_files.extend(evidence_dir.rglob("*_results_*.log"))

        existing_files = set(entry["file_path"] for entry in self.registry["evidence_entries"])

        for evidence_file in evidence_files:
            rel_path = str(evidence_file.relative_to(Path.cwd()))

            if rel_path not in existing_files:
                # Analyze evidence file
                evidence_type = self._determine_evidence_type(evidence_file)

                entry = {
                    "id": len(self.registry["evidence_entries"]) + 1,
                    "file_path": rel_path,
                    "evidence_type": evidence_type,
                    "created": datetime.fromtimestamp(evidence_file.stat().st_mtime).isoformat(),
                    "size": evidence_file.stat().st_size,
                    "registered": datetime.now().isoformat()
                }

                # Extract additional metadata if JSON
                if evidence_file.suffix == '.json':
                    try:
                        with open(evidence_file, 'r') as f:
                            data = json.load(f)
                            if "compliance_score" in data:
                                entry["compliance_score"] = data["compliance_score"]
                            if "violations" in data:
                                entry["violations_count"] = len(data["violations"])
                    except Exception:
                        pass

                self.registry["evidence_entries"].append(entry)
                new_entries += 1

        # Update statistics
        stats = self.registry["statistics"]
        stats["total_entries"] = len(self.registry["evidence_entries"])

        for entry in self.registry["evidence_entries"]:
            evidence_type = entry.get("evidence_type", "unknown")
            if "policy_review" in evidence_type:
                stats["policy_reviews"] += 1
            elif "structure" in evidence_type:
                stats["structure_validations"] += 1
            else:
                stats["compliance_checks"] += 1

        print(f"Registered {new_entries} new evidence files")
        return new_entries

    def _determine_evidence_type(self, file_path):
        """Determine evidence type from file path and name"""
        path_str = str(file_path).lower()

        if "policy_review" in path_str:
            return "policy_review"
        elif "structure" in path_str:
            return "structure_validation"
        elif "write_override" in path_str:
            return "write_override_registry"
        elif "test" in path_str:
            return "test_execution"
        elif "audit" in path_str:
            return "audit_log"
        else:
            return "compliance_evidence"

    def export_registry_log(self, output_path):
        """Export current registry as log file"""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        export_data = {
            "export_timestamp": datetime.now().isoformat(),
            "registry_version": self.registry["version"],
            "statistics": self.registry["statistics"],
            "recent_evidence": [
                entry for entry in self.registry["evidence_entries"][-10:]  # Last 10 entries
            ]
        }

        with open(output_path, 'w') as f:
            json.dump(export_data, f, indent=2)

        return output_path

def main():
    parser = argparse.ArgumentParser(description="Manage evidence registry")
    parser.add_argument("--scan", action="store_true", help="Scan and register new evidence")
    parser.add_argument("--out", help="Output log file path")

    args = parser.parse_args()

    registry = EvidenceRegistry()

    if args.scan:
        new_entries = registry.scan_and_register_evidence()
        registry._save_registry()
        print(f"Evidence registry updated with {new_entries} new entries")

    if args.out:
        log_file = registry.export_registry_log(args.out)
        print(f"Registry log exported to: {log_file}")

    # Print current statistics
    stats = registry.registry["statistics"]
    print(f"Registry statistics:")
    print(f"  Total entries: {stats['total_entries']}")
    print(f"  Policy reviews: {stats['policy_reviews']}")
    print(f"  Structure validations: {stats['structure_validations']}")
    print(f"  Compliance checks: {stats['compliance_checks']}")

if __name__ == "__main__":
    main()