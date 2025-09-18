#!/usr/bin/env python3
"""
CI Gate: Structure Lock Level 3 Validation
Version: 1.0
Date: 2025-09-15
Exit Code: 24 on violation
"""

import os
import sys
import subprocess
import yaml
import json
from pathlib import Path
from datetime import datetime


class StructureLockL3:
    """Level 3 structure validation for CI/CD pipeline"""

    def __init__(self):
        self.root_dir = Path(__file__).parent.parent.parent.parent
        self.errors = []
        self.warnings = []

    def validate_critical_files(self):
        """Validate that all critical files exist"""
        critical_files = [
            "12_tooling/scripts/structure_guard.sh",
            "12_tooling/hooks/pre_commit/structure_validation.sh",
            "23_compliance/policies/structure_policy.yaml",
            "23_compliance/exceptions/structure_exceptions.yaml",
            "23_compliance/tests/unit/test_structure_policy_vs_md.py",
            "24_meta_orchestration/triggers/ci/gates/structure_lock_l3.py"
        ]

        for file_path in critical_files:
            full_path = self.root_dir / file_path
            if not full_path.exists():
                self.errors.append(f"Missing critical file: {file_path}")

    def validate_24_modules(self):
        """Validate exactly 24 root modules exist"""
        expected_modules = [
            "01_ai_layer", "02_audit_logging", "03_core", "04_deployment",
            "05_documentation", "06_data_pipeline", "07_governance_legal",
            "08_identity_score", "09_meta_identity", "10_interoperability",
            "11_test_simulation", "12_tooling", "13_ui_layer", "14_zero_time_auth",
            "15_infra", "16_codex", "17_observability", "18_data_layer",
            "19_adapters", "20_foundation", "21_post_quantum_crypto",
            "22_datasets", "23_compliance", "24_meta_orchestration"
        ]

        for module in expected_modules:
            module_path = self.root_dir / module
            if not module_path.exists():
                self.errors.append(f"Missing module directory: {module}")
            elif not module_path.is_dir():
                self.errors.append(f"Module path is not a directory: {module}")

    def validate_module_structure(self):
        """Validate each module has required structure"""
        modules = [d for d in self.root_dir.iterdir()
                  if d.is_dir() and d.name.startswith(('01_', '02_', '03_', '04_', '05_',
                                                      '06_', '07_', '08_', '09_', '10_',
                                                      '11_', '12_', '13_', '14_', '15_',
                                                      '16_', '17_', '18_', '19_', '20_',
                                                      '21_', '22_', '23_', '24_'))]

        required_files = ["module.yaml", "README.md"]
        required_dirs = ["docs", "src", "tests"]

        for module in modules:
            for file in required_files:
                file_path = module / file
                if not file_path.exists():
                    self.warnings.append(f"Missing {file} in {module.name}")

            for dir_name in required_dirs:
                dir_path = module / dir_name
                if not dir_path.exists():
                    self.warnings.append(f"Missing {dir_name}/ directory in {module.name}")

    def run_structure_guard(self):
        """Run structure guard validation"""
        try:
            script_path = self.root_dir / "12_tooling/scripts/structure_guard.sh"
            result = subprocess.run(
                [str(script_path), "validate"],
                cwd=str(self.root_dir),
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                self.errors.append(f"Structure guard validation failed: {result.stderr}")

        except Exception as e:
            self.errors.append(f"Failed to run structure guard: {str(e)}")

    def generate_evidence(self):
        """Generate evidence for compliance"""
        evidence = {
            "timestamp": datetime.now().isoformat(),
            "validation_type": "structure_lock_l3",
            "errors": self.errors,
            "warnings": self.warnings,
            "status": "PASS" if not self.errors else "FAIL"
        }

        evidence_dir = self.root_dir / "23_compliance/evidence/ci_runs/structure_validation_results"
        evidence_dir.mkdir(parents=True, exist_ok=True)

        evidence_file = evidence_dir / f"structure_lock_l3_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(evidence_file, 'w') as f:
            json.dump(evidence, f, indent=2)

        return evidence

    def run_validation(self):
        """Run complete structure validation"""
        print("SSID OpenCore - Structure Lock L3 Validation")
        print("=" * 50)

        self.validate_critical_files()
        self.validate_24_modules()
        self.validate_module_structure()
        self.run_structure_guard()

        evidence = self.generate_evidence()

        # Report results
        if self.errors:
            print(f"\n❌ VALIDATION FAILED - {len(self.errors)} errors")
            for error in self.errors:
                print(f"  ERROR: {error}")

        if self.warnings:
            print(f"\n⚠️  WARNINGS - {len(self.warnings)} warnings")
            for warning in self.warnings:
                print(f"  WARNING: {warning}")

        if not self.errors and not self.warnings:
            print("\n✅ VALIDATION PASSED - All structure checks successful")

        print(f"\nEvidence saved to: {evidence}")

        # Exit with appropriate code
        if self.errors:
            sys.exit(24)  # Exit code 24 on violation as specified
        else:
            sys.exit(0)


if __name__ == "__main__":
    validator = StructureLockL3()
    validator.run_validation()