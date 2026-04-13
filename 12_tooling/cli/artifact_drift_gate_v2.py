#!/usr/bin/env python3
"""
Artifact Drift Gate v2 — Unified artifact integrity enforcement across all repos.

Enforces:
  1. Drift detection: SHA256 hash verification between SoT and deployment paths
  2. Dead artifact detection: Finds and reports stale/orphaned artifacts
  3. Cross-repo tamper detection: Verifies hash consistency across SSID, SSID-EMS, SSID-open-core, SSID-orchestrator

Exit codes:
  0 = PASS (all checks clean)
  1 = FAIL (artifacts drifted, dead, or tampered)
  2 = ERROR (gate execution error)
"""
from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class GateFinding:
    """Unified finding across G019/G020/G021."""
    gate: str  # "DRIFT", "DEAD", "TAMPER"
    path: str
    detail: str
    severity: str = "warning"
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


class ArtifactDriftGateV2:
    """Unified gate for G019, G020, G021."""

    def __init__(self, repo_root: str | Path = "."):
        self.repo_root = Path(repo_root)
        self.sot_dir = self.repo_root / "24_meta_orchestration" / "contracts"
        self.deploy_dir = self.repo_root / "12_tooling" / "testnet_mvp" / "01_hash_only_proof_registry" / "contracts"
        self.findings: list[GateFinding] = []
        self.workspace_root = self._find_workspace_root()

    def _find_workspace_root(self) -> Path:
        """Find SSID-Workspace root."""
        current = self.repo_root
        while current != current.parent:
            if (current.parent / "SSID" / ".git").exists():
                return current.parent
            if (current / "SSID" / ".git").exists():
                return current
            current = current.parent
        return self.repo_root

    def _sha256(self, path: Path) -> str:
        """Calculate SHA256 of file."""
        try:
            return hashlib.sha256(path.read_bytes()).hexdigest()
        except Exception as e:
            return f"ERROR:{str(e)}"

    # ============================================================
    # G019: Artifact Drift Detection
    # ============================================================
    def check_sot_deploy_drift(self) -> list[GateFinding]:
        """Check SoT vs deployment artifact drift (G019)."""
        drift_findings = []
        artifact_files = [
            "proof_registry_abi.json",
            "proof_registry_bytecode.json",
        ]

        for fname in artifact_files:
            sot_path = self.sot_dir / fname
            deploy_path = self.deploy_dir / fname

            if not sot_path.exists():
                drift_findings.append(GateFinding(
                    gate="DRIFT",
                    path=str(sot_path.relative_to(self.repo_root)),
                    detail=f"SoT artifact missing: {fname}",
                    severity="critical",
                ))
                continue

            if not deploy_path.exists():
                drift_findings.append(GateFinding(
                    gate="DRIFT",
                    path=str(deploy_path.relative_to(self.repo_root)),
                    detail=f"Deploy artifact missing: {fname}",
                    severity="critical",
                ))
                continue

            sot_hash = self._sha256(sot_path)
            deploy_hash = self._sha256(deploy_path)

            if sot_hash != deploy_hash:
                drift_findings.append(GateFinding(
                    gate="DRIFT",
                    path=fname,
                    detail=f"Hash mismatch: SoT={sot_hash[:16]}... vs deploy={deploy_hash[:16]}...",
                    severity="critical",
                ))

        return drift_findings

    # ============================================================
    # G020: Dead Artifact Detection
    # ============================================================
    def check_dead_artifacts(self) -> list[GateFinding]:
        """Scan for dead/orphaned artifacts (G020)."""
        dead_findings = []
        skip_dirs = {"__pycache__", ".git", "node_modules", ".venv", "venv", ".tox", ".pytest_cache"}

        # Check for empty files
        for fpath in self.repo_root.rglob("*"):
            if any(skip in fpath.parts for skip in skip_dirs):
                continue
            if not fpath.is_file():
                continue

            # Skip __init__.py and .gitkeep
            if fpath.name in ("__init__.py", ".gitkeep"):
                continue

            if fpath.stat().st_size == 0:
                dead_findings.append(GateFinding(
                    gate="DEAD",
                    path=str(fpath.relative_to(self.repo_root)),
                    detail="Empty file (0 bytes)",
                    severity="warning",
                ))

        # Check for placeholder files (< 50 bytes, only comments)
        comment_patterns = [r"^\s*#", r"^\s*//", r"^\s*<!--", r"^\s*$"]
        for fpath in self.repo_root.glob("**/*.py"):
            if any(skip in fpath.parts for skip in skip_dirs):
                continue
            if fpath.name == "__init__.py":
                continue

            try:
                size = fpath.stat().st_size
                if 0 < size < 50:
                    content = fpath.read_text(encoding="utf-8", errors="replace")
                    lines = [l.strip() for l in content.splitlines() if l.strip()]
                    if all(any(c in l for c in ["#", "//"]) for l in lines):
                        dead_findings.append(GateFinding(
                            gate="DEAD",
                            path=str(fpath.relative_to(self.repo_root)),
                            detail=f"Placeholder file ({size} bytes, only comments)",
                            severity="info",
                        ))
            except Exception:
                pass

        return dead_findings

    # ============================================================
    # G021: Cross-Repo Tamper Detection
    # ============================================================
    def check_cross_repo_tamper(self) -> list[GateFinding]:
        """Verify hash consistency across all repos (G021)."""
        tamper_findings = []

        # Key files to verify across repos
        cross_repo_keys = {
            "CLAUDE.md": "CLAUDE.md",
            "12_tooling/cli/sot_diff_alert.py": "12_tooling/cli/sot_diff_alert.py",
            "23_compliance/policies/registry": "23_compliance/policies/registry",
        }

        repos_to_check = ["SSID", "SSID-EMS", "SSID-open-core", "SSID-orchestrator"]
        hashes_by_file: dict[str, dict[str, str]] = {}

        for repo_name in repos_to_check:
            repo_path = self.workspace_root / repo_name
            if not repo_path.exists():
                tamper_findings.append(GateFinding(
                    gate="TAMPER",
                    path=repo_name,
                    detail="Repo not found in workspace",
                    severity="warning",
                ))
                continue

            for key_file, relative_path in cross_repo_keys.items():
                full_path = repo_path / relative_path
                if not full_path.exists():
                    continue

                # Calculate hash
                file_hash = self._sha256(full_path)
                if key_file not in hashes_by_file:
                    hashes_by_file[key_file] = {}
                hashes_by_file[key_file][repo_name] = file_hash

        # Compare hashes across repos for each file
        for key_file, repo_hashes in hashes_by_file.items():
            if len(repo_hashes) > 1:
                first_hash = next(iter(repo_hashes.values()))
                for repo_name, file_hash in repo_hashes.items():
                    if file_hash != first_hash:
                        tamper_findings.append(GateFinding(
                            gate="TAMPER",
                            path=f"{repo_name}/{key_file}",
                            detail=f"Hash mismatch across repos: {file_hash[:16]}... vs canonical {first_hash[:16]}...",
                            severity="critical",
                        ))

        return tamper_findings

    # ============================================================
    # Unified Execution & Reporting
    # ============================================================
    def run_all_gates(self) -> int:
        """Run all three gates (G019, G020, G021)."""
        print("=" * 70)
        print("Artifact Drift Gate v2 — G019, G020, G021 Unified Enforcement")
        print("=" * 70)

        # G019: Drift
        print("\n[G019] Checking SoT ↔ Deploy Drift...")
        drift = self.check_sot_deploy_drift()
        self.findings.extend(drift)
        print(f"       Found {len(drift)} drift issue(s)")

        # G020: Dead Artifacts
        print("[G020] Scanning for Dead Artifacts...")
        dead = self.check_dead_artifacts()
        self.findings.extend(dead)
        print(f"       Found {len(dead)} dead artifact(s)")

        # G021: Cross-Repo Tamper
        print("[G021] Verifying Cross-Repo Hash Integrity...")
        tamper = self.check_cross_repo_tamper()
        self.findings.extend(tamper)
        print(f"       Found {len(tamper)} tamper incident(s)")

        # Report
        print("\n" + "=" * 70)
        print("FINDINGS SUMMARY")
        print("=" * 70)

        if not self.findings:
            print("\nSUCCESS: All gates passed. No drift, dead artifacts, or tampering detected.")
            return 0

        by_gate = {}
        for f in self.findings:
            by_gate.setdefault(f.gate, []).append(f)

        for gate in ["DRIFT", "DEAD", "TAMPER"]:
            if gate not in by_gate:
                continue
            items = by_gate[gate]
            print(f"\n[{gate}] ({len(items)} findings)")
            for item in items:
                sev_tag = f"[{item.severity.upper()}]" if item.severity != "info" else "[info]"
                print(f"  {sev_tag} {item.path}")
                print(f"         {item.detail}")

        # Determine exit code based on severity
        critical_count = sum(1 for f in self.findings if f.severity == "critical")
        print(f"\n{'='*70}")
        print(f"RESULT: {len(self.findings)} total findings ({critical_count} critical)")

        if critical_count > 0:
            print("STATUS: FAIL — Critical findings must be resolved")
            return 1
        else:
            print("STATUS: PASS WITH WARNINGS — Review info/warning findings")
            return 0

    def export_json(self, output_path: str | Path):
        """Export findings as JSON for CI/CD integration."""
        output_path = Path(output_path)
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_findings": len(self.findings),
            "by_gate": {},
            "findings": [asdict(f) for f in self.findings],
        }

        for f in self.findings:
            if f.gate not in report["by_gate"]:
                report["by_gate"][f.gate] = {"count": 0, "critical": 0}
            report["by_gate"][f.gate]["count"] += 1
            if f.severity == "critical":
                report["by_gate"][f.gate]["critical"] += 1

        output_path.write_text(json.dumps(report, indent=2))
        print(f"\nFindings exported to: {output_path}")


def main():
    gate = ArtifactDriftGateV2()
    exit_code = gate.run_all_gates()

    # Export JSON report
    output = Path("/tmp/artifact_drift_gate_v2_report.json")
    gate.export_json(output)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
