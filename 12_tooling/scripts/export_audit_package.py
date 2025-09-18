#!/usr/bin/env python3
"""
Audit Package Export System
Version: 1.0
Date: 2025-09-16

Creates comprehensive audit packages for compliance reporting.
"""

import argparse
import json
import tarfile
import hashlib
import os
import sys
from datetime import datetime
from pathlib import Path

class AuditExporter:
    def __init__(self):
        self.export_types = {
            'EU': 'European Union GDPR/Compliance',
            'ISO': 'ISO 27001 Security Standards',
            'SOC2': 'SOC 2 Type II Controls',
            'PROTECTION': 'Protection System Export'
        }

    def _collect_evidence_files(self, evidence_dir):
        """Collect all evidence files"""
        evidence_files = []
        evidence_path = Path(evidence_dir)

        if not evidence_path.exists():
            print(f"Warning: Evidence directory not found: {evidence_dir}")
            return evidence_files

        # Collect JSON evidence files
        for pattern in ['*_evidence_*.json', '*_log_*.json', '*_results_*.log']:
            evidence_files.extend(evidence_path.rglob(pattern))

        return evidence_files

    def _collect_policy_files(self):
        """Collect policy and configuration files"""
        policy_files = []

        # Policy files
        policy_dir = Path("23_compliance/policies")
        if policy_dir.exists():
            policy_files.extend(policy_dir.glob("*.yaml"))
            policy_files.extend(policy_dir.glob("*.yml"))

        # Configuration files
        config_files = [
            "12_tooling/scripts/structure_guard.sh",
            "12_tooling/hooks/pre_commit/structure_validation.sh",
            ".git/hooks/pre-commit"
        ]

        for config_file in config_files:
            config_path = Path(config_file)
            if config_path.exists():
                policy_files.append(config_path)

        return policy_files

    def _collect_protection_files(self):
        """Collect protection system files"""
        protection_files = []

        # Core protection scripts
        protection_paths = [
            "12_tooling/scripts/",
            "12_tooling/hooks/",
            "23_compliance/",
            "05_documentation/security/"
        ]

        for path in protection_paths:
            path_obj = Path(path)
            if path_obj.exists():
                if path_obj.is_dir():
                    protection_files.extend(path_obj.rglob("*"))
                else:
                    protection_files.append(path_obj)

        return [f for f in protection_files if f.is_file()]

    def _generate_manifest(self, export_type, files, output_path):
        """Generate export manifest"""
        manifest = {
            "export_info": {
                "type": export_type,
                "description": self.export_types.get(export_type, "Unknown"),
                "created": datetime.now().isoformat(),
                "version": "1.0"
            },
            "system_info": {
                "project": "SSID OpenCore",
                "structure_version": "24-module",
                "compliance_framework": export_type
            },
            "files": [],
            "checksums": {}
        }

        for file_path in files:
            rel_path = file_path.relative_to(Path.cwd())
            file_info = {
                "path": str(rel_path),
                "size": file_path.stat().st_size,
                "modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
            }

            # Calculate file hash
            with open(file_path, 'rb') as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
                file_info["sha256"] = file_hash
                manifest["checksums"][str(rel_path)] = file_hash

            manifest["files"].append(file_info)

        # Save manifest
        manifest_path = Path(f"{output_path}.manifest.json")
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)

        return manifest_path

    def export_audit_package(self, export_type, evidence_dir, output_path):
        """Create audit export package"""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        files_to_export = []

        if export_type == 'PROTECTION':
            files_to_export = self._collect_protection_files()
            print(f"Collected {len(files_to_export)} protection files")
        else:
            # Collect evidence and policy files for compliance exports
            evidence_files = self._collect_evidence_files(evidence_dir)
            policy_files = self._collect_policy_files()
            files_to_export = evidence_files + policy_files
            print(f"Collected {len(evidence_files)} evidence files and {len(policy_files)} policy files")

        if not files_to_export:
            print("Warning: No files found for export")
            return None

        # Generate manifest
        manifest_path = self._generate_manifest(export_type, files_to_export, output_path)
        files_to_export.append(manifest_path)

        # Create tar.gz archive
        with tarfile.open(output_path, 'w:gz') as tar:
            for file_path in files_to_export:
                arcname = file_path.relative_to(Path.cwd())
                tar.add(file_path, arcname=arcname)

        # Generate SHA256 checksum
        with open(output_path, 'rb') as f:
            package_hash = hashlib.sha256(f.read()).hexdigest()

        checksum_path = Path(f"{output_path}.sha256")
        with open(checksum_path, 'w') as f:
            f.write(f"{package_hash}  {output_path.name}\n")

        print(f"Audit package created: {output_path}")
        print(f"Package size: {output_path.stat().st_size} bytes")
        print(f"Files included: {len(files_to_export)}")
        print(f"SHA256 checksum: {checksum_path}")

        # Clean up temporary manifest
        if manifest_path.exists():
            manifest_path.unlink()

        return output_path

    def _generate_score_log(self, output_path):
        """Generate score trend log"""
        try:
            # Run structure guard to get current score
            result = subprocess.run(
                ['bash', '12_tooling/scripts/structure_guard.sh', 'score'],
                capture_output=True, text=True
            )
            current_score = int(result.stdout.strip())

            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "score": current_score,
                "status": "COMPLIANT" if current_score >= 95 else "NON-COMPLIANT",
                "trend": "stable"  # Would need historical data for real trend analysis
            }

            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, 'w') as f:
                json.dump(log_entry, f, indent=2)

            return output_path

        except Exception as e:
            print(f"Error generating score log: {e}")
            return None

def main():
    parser = argparse.ArgumentParser(description="Export audit packages")
    parser.add_argument("--type", required=True, help="Export type (EU,ISO,SOC2,PROTECTION)")
    parser.add_argument("--evidence-dir", default="23_compliance/evidence/", help="Evidence directory")
    parser.add_argument("--out", required=True, help="Output file path")

    args = parser.parse_args()

    exporter = AuditExporter()

    # Handle multiple types
    export_types = args.type.split(',')

    for export_type in export_types:
        export_type = export_type.strip()
        if export_type not in exporter.export_types:
            print(f"Unknown export type: {export_type}")
            continue

        # Generate output path for this type
        output_base = Path(args.out)
        if len(export_types) > 1:
            # Multiple types - create separate files
            output_path = output_base.parent / f"{output_base.stem}_{export_type}{output_base.suffix}"
        else:
            output_path = output_base

        result = exporter.export_audit_package(export_type, args.evidence_dir, output_path)
        if result:
            print(f"{export_type} audit package exported successfully")

if __name__ == "__main__":
    main()