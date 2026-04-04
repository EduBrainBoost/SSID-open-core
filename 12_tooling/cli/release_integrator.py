#!/usr/bin/env python3
"""
SSID ReleaseIntegrator v4.1 - Mechanical Patch Application
B1: ReleaseIntegrator role - applies verified patches mechanically
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

# SSID Configuration
REPO_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_ROOT = REPO_ROOT / "02_audit_logging" / "evidence" / "releases"
BACKUP_ROOT = REPO_ROOT / "02_audit_logging" / "backups"
CANONICAL_SOT_FILES = [
    "03_core/validators/sot/sot_validator_core.py",
    "23_compliance/policies/sot/sot_policy.rego",
    "16_codex/contracts/sot/sot_contract.yaml",
    "12_tooling/cli/sot_validator.py",
    "11_test_simulation/tests_compliance/test_sot_validator.py",
    "02_audit_logging/reports/SOT_MOSCOW_ENFORCEMENT_V3.2.0.md",
]


class ReleaseIntegrator:
    """Mechanical patch application with full verification"""

    def __init__(self, repo_root: Path | None = None):
        self.repo_root = repo_root or REPO_ROOT
        self.evidence_root = EVIDENCE_ROOT
        self.backup_root = BACKUP_ROOT

    def _sha256_file(self, path: Path) -> str:
        """Calculate SHA256 of file"""
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    def _utc_ts(self) -> str:
        """UTC timestamp"""
        return datetime.datetime.now(datetime.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    def _validate_patch_bundle(self, evidence_dir: Path) -> dict[str, Any]:
        """Validate patch bundle structure and integrity"""
        required_files = ["patch.diff", "patch.sha256", "manifest.json", "gate_status.json"]
        missing = [f for f in required_files if not (evidence_dir / f).exists()]
        if missing:
            raise ValueError(f"RELEASE_INTEGRATOR_FAIL: missing files in bundle: {missing}")

        # Verify patch integrity
        patch_file = evidence_dir / "patch.diff"
        expected_sha = (evidence_dir / "patch.sha256").read_text().strip()
        actual_sha = self._sha256_file(patch_file)
        if expected_sha != actual_sha:
            raise ValueError("RELEASE_INTEGRATOR_FAIL: patch integrity mismatch")

        # Load and validate manifest
        manifest = json.loads((evidence_dir / "manifest.json").read_text())
        gate_status = json.loads((evidence_dir / "gate_status.json").read_text())

        # Verify all gates passed
        if gate_status.get("overall_status") != "PASS":
            failed_gates = [g["name"] for g in gate_status.get("gates", []) if g.get("status") != "PASS"]
            raise ValueError(f"RELEASE_INTEGRATOR_FAIL: gates failed: {failed_gates}")

        return {
            "manifest": manifest,
            "gate_status": gate_status,
            "patch_file": patch_file,
            "task_id": manifest.get("task_id"),
            "changed_paths": manifest.get("changed_paths", []),
        }

    def _create_backup(self, task_id: str) -> Path:
        """Create backup of repository before patch application"""
        backup_dir = self.backup_root / f"{task_id}_{self._utc_ts().replace(':', '').replace('-', '')}"
        backup_dir.mkdir(parents=True, exist_ok=True)

        # Backup only changed files
        evidence_dir = self.evidence_root / task_id
        if evidence_dir.exists():
            manifest = json.loads((evidence_dir / "manifest.json").read_text())
            changed_paths = manifest.get("changed_paths", [])

            backup_manifest = {
                "task_id": task_id,
                "backup_utc": self._utc_ts(),
                "changed_paths": changed_paths,
                "backup_files": [],
            }

            for rel_path in changed_paths:
                src = self.repo_root / rel_path
                if src.exists():
                    dst = backup_dir / rel_path
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                    backup_manifest["backup_files"].append(
                        {"path": rel_path, "sha256": self._sha256_file(src), "bytes": src.stat().st_size}
                    )

            (backup_dir / "backup_manifest.json").write_text(
                json.dumps(backup_manifest, indent=2, sort_keys=True), encoding="utf-8"
            )

        return backup_dir

    def _apply_patch(self, patch_file: Path, dry_run: bool = False) -> tuple[bool, str]:
        """Apply patch using system patch command"""
        cmd = ["patch", "-p1", "--dry-run" if dry_run else "", "-i", str(patch_file)]
        cmd = [c for c in cmd if c]  # Remove empty strings

        proc = subprocess.run(cmd, cwd=str(self.repo_root), capture_output=True, text=True, encoding="utf-8")

        if proc.returncode == 0:
            return True, proc.stdout
        else:
            return False, proc.stderr

    def _verify_soT_sync(self, changed_paths: list[str]) -> list[str]:  # noqa: N802
        """E3: Verify SoT artifact synchronization"""
        sot_touched = [p for p in changed_paths if p in CANONICAL_SOT_FILES]
        violations = []

        if sot_touched:
            # Check if all canonical SoT files exist and are consistent
            for sot_file in CANONICAL_SOT_FILES:
                if not (self.repo_root / sot_file).exists():
                    violations.append(f"SOT_SYNC_FAIL: missing canonical file {sot_file}")

            # Add more sophisticated SoT consistency checks here
            # For now, just verify existence

        return violations

    def _run_final_gates(self) -> tuple[bool, list[dict[str, Any]]]:
        """Run final gate chain after patch application"""
        # Use dispatcher gates for consistency
        cmd = [sys.executable, str(self.repo_root / "12_tooling" / "cli" / "ssid_dispatcher.py"), "gates"]
        proc = subprocess.run(cmd, cwd=str(self.repo_root), capture_output=True, text=True, encoding="utf-8")

        if proc.returncode == 0:
            return True, [{"name": "final_gates", "status": "PASS", "output": proc.stdout}]
        else:
            return False, [{"name": "final_gates", "status": "FAIL", "output": proc.stderr}]

    def _write_release_evidence(
        self,
        task_id: str,
        validation_result: dict[str, Any],
        backup_dir: Path,
        apply_result: tuple[bool, str],
        final_gates_result: tuple[bool, list[dict[str, Any]]],
    ) -> Path:
        """Write evidence for release integration"""
        ts = self._utc_ts().replace(":", "").replace("-", "")
        release_dir = self.evidence_root / f"release_{task_id}_{ts}"
        release_dir.mkdir(parents=True, exist_ok=True)

        release_evidence = {
            "release_id": f"release_{task_id}_{ts}",
            "task_id": task_id,
            "release_utc": self._utc_ts(),
            "security_context": "ROOT-24-LOCK",
            "validation_result": validation_result,
            "backup_directory": str(backup_dir.relative_to(self.repo_root)),
            "patch_apply_success": apply_result[0],
            "patch_apply_output": apply_result[1],
            "final_gates_success": final_gates_result[0],
            "final_gates_details": final_gates_result[1],
            "release_status": "SUCCESS" if (apply_result[0] and final_gates_result[0]) else "FAILED",
        }

        (release_dir / "release_manifest.json").write_text(
            json.dumps(release_evidence, indent=2, sort_keys=True), encoding="utf-8"
        )

        return release_dir

    def integrate_patch(self, evidence_dir: Path, dry_run: bool = False) -> int:
        """Main integration workflow"""
        try:
            # Step 1: Validate patch bundle
            print(f"INFO: Validating patch set: {evidence_dir}")
            validation_result = self._validate_patch_bundle(evidence_dir)
            task_id = validation_result["task_id"]
            changed_paths = validation_result["changed_paths"]
            print(f"INFO: Validated patch set for task {task_id}")

            # Step 2: Create backup
            print("INFO: Creating backup...")
            backup_dir = self._create_backup(task_id)
            print(f"INFO: Backup created: {backup_dir}")

            # Step 3: Verify SoT sync requirements
            print("INFO: Verifying SoT synchronization...")
            sot_violations = self._verify_soT_sync(changed_paths)
            if sot_violations:
                print("ERROR: SoT sync violations:")
                for v in sot_violations:
                    print(f"  - {v}")
                return 25

            # Step 4: Apply patch (or dry run)
            patch_file = validation_result["patch_file"]
            if dry_run:
                print("INFO: Dry run - testing patch application...")
            else:
                print("INFO: Applying patch...")

            apply_success, apply_output = self._apply_patch(patch_file, dry_run=dry_run)
            if not apply_success:
                print(f"ERROR: Patch application failed: {apply_output}")
                return 26

            print(f"INFO: Patch {'test successful' if dry_run else 'applied successfully'}")

            # Step 5: Run final gates (skip for dry run)
            if not dry_run:
                print("INFO: Running final gates...")
                final_gates_success, final_gates_details = self._run_final_gates()
                if not final_gates_success:
                    print("ERROR: Final gates failed")
                    for gate in final_gates_details:
                        print(f"  - {gate['name']}: {gate['status']}")
                    return 27

                print("INFO: Final gates passed")
            else:
                final_gates_success, final_gates_details = (
                    True,
                    [{"name": "final_gates", "status": "SKIPPED", "output": "Dry run mode"}],
                )

            # Step 6: Write release evidence
            release_dir = self._write_release_evidence(
                task_id,
                validation_result,
                backup_dir,
                (apply_success, apply_output),
                (final_gates_success, final_gates_details),
            )

            if dry_run:
                print(f"SUCCESS: Dry run completed - Release evidence: {release_dir}")
            else:
                print(f"SUCCESS: Patch integrated successfully - Release evidence: {release_dir}")

            return 0

        except Exception as e:
            print(f"ERROR: Release integration failed: {e}")
            return 28


def main() -> int:
    parser = argparse.ArgumentParser(description="SSID ReleaseIntegrator v4.1 - Mechanical Patch Application")
    parser.add_argument("evidence_dir", help="Path to task evidence directory containing patch set")
    parser.add_argument("--dry-run", action="store_true", help="Test patch application without applying")
    parser.add_argument("--repo-root", help="Repository root (default: auto-detect)")

    args = parser.parse_args()

    evidence_dir = Path(args.evidence_dir).resolve()
    if not evidence_dir.exists():
        print(f"ERROR: Evidence directory not found: {evidence_dir}")
        return 1

    repo_root = Path(args.repo_root).resolve() if args.repo_root else REPO_ROOT
    integrator = ReleaseIntegrator(repo_root)

    return integrator.integrate_patch(evidence_dir, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
