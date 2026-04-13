#!/usr/bin/env python3
"""
SSID Forensic Evidence Manager v4.1
Time-limited storage for FORENSIC mode with automatic cleanup
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ForensicConfig:
    """Configuration for forensic evidence management"""

    max_retention_hours: int = 72  # 3 days default
    evidence_root: Path
    forensic_subdir: str = "forensic"
    cleanup_interval_hours: int = 24
    compression_enabled: bool = True
    encryption_enabled: bool = False  # Future feature


class SSIDForensicManager:
    """Manages forensic evidence with time-limited storage"""

    def __init__(self, repo_root: Path, config: ForensicConfig | None = None):
        self.repo_root = repo_root
        self.config = config or ForensicConfig(evidence_root=repo_root / "02_audit_logging" / "evidence")
        self.forensic_root = self.config.evidence_root / self.config.forensic_subdir

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

    def _is_expired(self, evidence_dir: Path) -> bool:
        """Check if evidence directory is expired"""
        if not evidence_dir.exists():
            return True

        try:
            # Check modification time
            mod_time = datetime.datetime.fromtimestamp(evidence_dir.stat().st_mtime, datetime.UTC)
            expiry_time = datetime.datetime.now(datetime.UTC) - datetime.timedelta(
                hours=self.config.max_retention_hours
            )
            return mod_time < expiry_time
        except Exception:
            return True

    def _compress_evidence(self, evidence_dir: Path) -> Path:
        """Compress evidence directory"""
        if not self.config.compression_enabled:
            return evidence_dir

        compressed_path = evidence_dir.with_suffix(".tar.gz")
        if compressed_path.exists():
            return compressed_path

        try:
            # Create tar.gz archive
            subprocess.run(
                ["tar", "-czf", str(compressed_path), "-C", str(evidence_dir.parent), evidence_dir.name],
                check=True,
                capture_output=True,
            )

            # Verify compression
            if compressed_path.exists() and compressed_path.stat().st_size > 0:
                return compressed_path
        except subprocess.CalledProcessError:
            pass

        return evidence_dir

    def store_forensic_evidence(
        self, task_id: str, original_evidence: Path, prompt: str = "", stdout: str = "", stderr: str = ""
    ) -> Path:
        """Store forensic evidence with full content"""
        forensic_dir = self.forensic_root / f"forensic_{task_id}_{self._utc_ts().replace(':', '').replace('-', '')}"
        forensic_dir.mkdir(parents=True, exist_ok=True)

        # Copy original evidence
        if original_evidence.exists():
            if original_evidence.is_dir():
                shutil.copytree(original_evidence, forensic_dir / "original", dirs_exist_ok=True)
            else:
                shutil.copy2(original_evidence, forensic_dir / "original")

        # Store full forensic data (redacted but complete)
        if self.config.encryption_enabled:
            # Future: encrypt sensitive content
            pass

        # Import redactor if available
        try:
            sys.path.insert(0, str(self.repo_root / "03_core" / "security"))
            from data_minimization import SSIDRedactor

            redactor = SSIDRedactor("FORENSIC")
        except ImportError:
            redactor = None

        forensic_data = {
            "task_id": task_id,
            "mode": "FORENSIC",
            "created_utc": self._utc_ts(),
            "expires_utc": (
                datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=self.config.max_retention_hours)
            )
            .isoformat()
            .replace("+00:00", "Z"),
            "original_evidence": str(original_evidence.relative_to(self.repo_root)),
            "evidence_integrity": {},
        }

        # Store prompt (redacted)
        if prompt:
            if redactor:
                redacted_prompt = redactor.redact_text(prompt)
                forensic_data["prompt_sha256"] = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
            else:
                redacted_prompt = prompt
                forensic_data["prompt_sha256"] = hashlib.sha256(prompt.encode("utf-8")).hexdigest()

            (forensic_dir / "prompt_redacted.txt").write_text(redacted_prompt, encoding="utf-8")

        # Store stdout (redacted but complete)
        if stdout:
            redacted_stdout = redactor.redact_text(stdout) if redactor else stdout

            (forensic_dir / "stdout_redacted.txt").write_text(redacted_stdout, encoding="utf-8")
            forensic_data["stdout_sha256"] = hashlib.sha256(stdout.encode("utf-8")).hexdigest()

        # Store stderr (redacted but complete)
        if stderr:
            redacted_stderr = redactor.redact_text(stderr) if redactor else stderr

            (forensic_dir / "stderr_redacted.txt").write_text(redacted_stderr, encoding="utf-8")
            forensic_data["stderr_sha256"] = hashlib.sha256(stderr.encode("utf-8")).hexdigest()

        # Add redaction report
        if redactor:
            forensic_data["redaction_report"] = redactor.get_redaction_report()

        # Calculate evidence integrity hashes
        evidence_integrity = {}
        for file_path in forensic_dir.rglob("*"):
            if file_path.is_file():
                rel_path = file_path.relative_to(forensic_dir)
                evidence_integrity[str(rel_path)] = self._sha256_file(file_path)

        forensic_data["evidence_integrity"] = evidence_integrity

        # Write forensic manifest
        (forensic_dir / "forensic_manifest.json").write_text(
            json.dumps(forensic_data, indent=2, sort_keys=True), encoding="utf-8"
        )

        # Compress if enabled
        compressed_path = self._compress_evidence(forensic_dir)
        if compressed_path != forensic_dir:
            # Remove original uncompressed directory
            shutil.rmtree(forensic_dir)
            return compressed_path

        return forensic_dir

    def cleanup_expired_evidence(self, dry_run: bool = False) -> dict[str, Any]:
        """Clean up expired forensic evidence"""
        if not self.forensic_root.exists():
            return {"cleaned": 0, "freed_bytes": 0, "errors": []}

        cleaned = 0
        freed_bytes = 0
        errors = []

        for item in self.forensic_root.iterdir():
            if item.name.startswith("forensic_"):
                expired = self._is_expired(item)

                if expired:
                    try:
                        # Calculate size before deletion
                        if item.is_dir():
                            total_size = sum(f.stat().st_size for f in item.rglob("*") if f.is_file())
                        else:
                            total_size = item.stat().st_size

                        if not dry_run:
                            if item.is_dir():
                                shutil.rmtree(item)
                            else:
                                item.unlink()

                        cleaned += 1
                        freed_bytes += total_size

                    except Exception as e:
                        errors.append(f"Failed to cleanup {item}: {e}")

        cleanup_report = {
            "cleanup_timestamp": self._utc_ts(),
            "dry_run": dry_run,
            "max_retention_hours": self.config.max_retention_hours,
            "cleaned_items": cleaned,
            "freed_bytes": freed_bytes,
            "freed_mb": round(freed_bytes / (1024 * 1024), 2),
            "errors": errors,
        }

        return cleanup_report

    def list_forensic_evidence(self) -> list[dict[str, Any]]:
        """List all forensic evidence with status"""
        evidence_list = []

        if not self.forensic_root.exists():
            return evidence_list

        for item in self.forensic_root.iterdir():
            if item.name.startswith("forensic_"):
                try:
                    # Load forensic manifest
                    manifest_path = (
                        item / "forensic_manifest.json"
                        if item.is_dir()
                        else item.with_suffix(".tar.gz").parent / "forensic_manifest.json"
                    )

                    if manifest_path.exists():
                        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    else:
                        # Try to extract from compressed archive
                        if item.suffix == ".gz":
                            # Extract manifest from tar.gz
                            try:
                                result = subprocess.run(
                                    ["tar", "-xzf", str(item), "--to-stdout", "forensic_manifest.json"],
                                    capture_output=True,
                                    text=True,
                                    cwd=str(item.parent),
                                )
                                if result.returncode == 0:
                                    manifest = json.loads(result.stdout)
                                else:
                                    continue
                            except Exception:
                                continue
                        else:
                            continue

                    # Add status information
                    evidence_info = {
                        "task_id": manifest.get("task_id", "unknown"),
                        "evidence_path": str(item.relative_to(self.repo_root)),
                        "created_utc": manifest.get("created_utc"),
                        "expires_utc": manifest.get("expires_utc"),
                        "expired": self._is_expired(item),
                        "mode": manifest.get("mode", "FORENSIC"),
                        "size_bytes": item.stat().st_size if item.exists() else 0,
                        "compressed": item.suffix == ".gz",
                    }

                    evidence_list.append(evidence_info)

                except Exception:
                    # Skip problematic evidence
                    continue

        # Sort by creation time (newest first)
        evidence_list.sort(key=lambda x: x.get("created_utc", ""), reverse=True)
        return evidence_list

    def schedule_cleanup(self) -> None:
        """Schedule automatic cleanup (e.g., via cron)"""
        cleanup_script = self.repo_root / "02_audit_logging" / "scripts" / "forensic_cleanup.sh"
        cleanup_script.parent.mkdir(parents=True, exist_ok=True)

        script_content = f"""#!/bin/bash
# SSID Forensic Evidence Cleanup Script
# Auto-generated - DO NOT EDIT MANUALLY

set -euo pipefail

REPO_ROOT="{self.repo_root}"
PYTHON="{sys.executable}"
MAX_HOURS={self.config.max_retention_hours}

echo "INFO: Starting forensic evidence cleanup at $(date -u)"

# Run cleanup
$PYTHON -c "
import sys
sys.path.insert(0, str('$REPO_ROOT/03_core/security'))
from forensic_manager import SSIDForensicManager, ForensicConfig

config = ForensicConfig(
    max_retention_hours=$MAX_HOURS,
    evidence_root=Path('$REPO_ROOT/02_audit_logging/evidence')
)
manager = SSIDForensicManager(Path('$REPO_ROOT'), config)
report = manager.cleanup_expired_evidence()

print(f'Cleaned {{report["cleaned_items"]}} items')
print(f'Freed {{report["freed_mb"]}} MB')
if report['errors']:
    print('Errors:', report['errors'])
"

echo "INFO: Forensic cleanup completed"
"""

        cleanup_script.write_text(script_content, encoding="utf-8")
        cleanup_script.chmod(0o755)

        print(f"Cleanup script created: {cleanup_script}")
        print("Add to crontab for automatic cleanup:")
        print(f"0 */{self.config.cleanup_interval_hours} * * * {cleanup_script}")


def main() -> int:
    parser = argparse.ArgumentParser(description="SSID Forensic Evidence Manager v4.1")
    parser.add_argument("--store", help="Store forensic evidence (task_id, evidence_dir)")
    parser.add_argument("--list", action="store_true", help="List all forensic evidence")
    parser.add_argument("--cleanup", action="store_true", help="Cleanup expired evidence")
    parser.add_argument("--dry-run", action="store_true", help="Dry run for cleanup")
    parser.add_argument("--schedule-cleanup", action="store_true", help="Generate cleanup script")
    parser.add_argument("--max-hours", type=int, default=72, help="Maximum retention hours")
    parser.add_argument("--repo-root", help="Repository root (default: auto-detect)")

    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve() if args.repo_root else Path(__file__).resolve().parents[2]
    config = ForensicConfig(
        max_retention_hours=args.max_hours, evidence_root=repo_root / "02_audit_logging" / "evidence"
    )
    manager = SSIDForensicManager(repo_root, config)

    if args.store:
        parts = args.store.split(",", 2)
        if len(parts) < 2:
            print("ERROR: --store requires task_id,evidence_dir[,prompt,stdout,stderr]")
            return 1

        task_id = parts[0]
        evidence_dir = Path(parts[1])
        prompt = parts[2] if len(parts) > 2 else ""
        # stdout and stderr would need more complex parsing

        forensic_path = manager.store_forensic_evidence(task_id, evidence_dir, prompt)
        print(f"Forensic evidence stored: {forensic_path}")

    elif args.list:
        evidence_list = manager.list_forensic_evidence()

        if not evidence_list:
            print("No forensic evidence found.")
            return 0

        print(f"\\nSSID Forensic Evidence (max retention: {args.max_hours} hours)")
        print("-" * 80)

        for evidence in evidence_list:
            status = "EXPIRED" if evidence["expired"] else "ACTIVE"
            comp = "COMPRESSED" if evidence["compressed"] else "UNCOMPRESSED"

            print(f"Task ID: {evidence['task_id']}")
            print(f"Path: {evidence['evidence_path']}")
            print(f"Created: {evidence['created_utc']}")
            print(f"Expires: {evidence['expires_utc']}")
            print(f"Status: {status} | {comp}")
            print(f"Size: {evidence['size_bytes']} bytes")
            print("-" * 40)

        active_count = len([e for e in evidence_list if not e["expired"]])
        expired_count = len(evidence_list) - active_count

        print(f"\\nSummary: {active_count} active, {expired_count} expired")

    elif args.cleanup or args.dry_run:
        report = manager.cleanup_expired_evidence(dry_run=args.dry_run)

        mode = "DRY RUN" if args.dry_run else "CLEANUP"
        print(f"\\nSSID Forensic Evidence {mode}")
        print(f"Timestamp: {report['cleanup_timestamp']}")
        print(f"Max retention: {report['max_retention_hours']} hours")
        print(f"Items cleaned: {report['cleaned_items']}")
        print(f"Space freed: {report['freed_mb']} MB")

        if report["errors"]:
            print("Errors:")
            for error in report["errors"]:
                print(f"  - {error}")

        if args.dry_run:
            print("\\nRun with --cleanup to actually delete files.")

    elif args.schedule_cleanup:
        manager.schedule_cleanup()

    else:
        parser.print_help()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
