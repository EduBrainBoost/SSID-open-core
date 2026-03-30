# DEPRECATED: REDUNDANT — Canonical tool is 12_tooling/cli/sot_enforcement_gate.py
#!/usr/bin/env python3
"""
sot_runtime_enforcement_gate.py — Unified SoT Runtime Enforcement Gate.

Combines:
  - SoT contract validation (sot_validator_core.py)
  - Spec file enforcement (all required keys, forbidden paths, allowlists)
  - Phase 3 contract artifact integrity (ABI/bytecode hash verification)
  - .sol file prohibition check

Produces: JSON report, optional MD report, PASS/FAIL exit code.

Usage:
  python 12_tooling/cli/sot_runtime_enforcement_gate.py [options]

Options:
  --repo-root PATH       Path to SSID repo root (default: auto-detect)
  --fail-on-drift        Exit 1 if any drift is detected (implies all checks)
  --write-reports        Write JSON + MD reports to 02_audit_logging/reports/
  --json-only            Output JSON report to stdout and exit
  --check-sot            Run SoT contract validation (default: True)
  --check-artifacts      Check Phase 3 contract artifact integrity (default: True)
  --check-no-sol         Verify no .sol files exist in repo (default: True)

Exit codes:
  0  — PASS: no violations detected
  1  — FAIL: drift or violations detected (or --fail-on-drift triggered)
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Repo root detection
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]

# Canonical paths
_SOT_CORE_PATH = _REPO_ROOT / "03_core" / "validators" / "sot" / "sot_validator_core.py"
_CONTRACTS_DIR = _REPO_ROOT / "24_meta_orchestration" / "contracts"
_ABI_PATH = _CONTRACTS_DIR / "proof_registry_abi.json"
_BYTECODE_PATH = _CONTRACTS_DIR / "proof_registry_bytecode.json"
_MANIFEST_PATH = _CONTRACTS_DIR / "compiler_manifest.json"
_REPORT_DIR = _REPO_ROOT / "02_audit_logging" / "reports"

GATE_VERSION = "2.0.0"
GATE_NAME = "sot_runtime_enforcement_gate"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _file_sha256(path: Path) -> str:
    """Return sha256 hex digest of a file, or 'MISSING' if not found."""
    if not path.is_file():
        return "MISSING"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _file_sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_sot_core(repo_root: Path):
    """Load sot_validator_core.py via importlib. Returns module or None."""
    core_path = repo_root / "03_core" / "validators" / "sot" / "sot_validator_core.py"
    if not core_path.is_file():
        return None
    try:
        sys.modules.pop("sot_validator_core", None)
        spec = importlib.util.spec_from_file_location("sot_validator_core", str(core_path))
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Check: SoT contract validation
# ---------------------------------------------------------------------------


def _check_sot_contract(repo_root: Path) -> Dict[str, Any]:
    """Run the SoT validator core and return a structured check result."""
    result: Dict[str, Any] = {
        "check": "sot_contract_validation",
        "status": "UNKNOWN",
        "violations": [],
        "passed_rules": [],
        "rules_checked": 0,
    }

    mod = _load_sot_core(repo_root)
    if mod is None:
        result["status"] = "FAIL"
        result["violations"].append({
            "rule_id": "GATE_SOT_001",
            "message": f"sot_validator_core.py not found at {_SOT_CORE_PATH}",
        })
        return result

    try:
        validator = mod.SoTValidatorCore(str(repo_root))
        results = validator.validate_all()
        ok, failed = validator.evaluate_priorities(results)
    except Exception as exc:
        result["status"] = "FAIL"
        result["violations"].append({
            "rule_id": "GATE_SOT_002",
            "message": f"SoT validator raised exception: {exc}",
        })
        return result

    for rule_id, data in sorted(results.items()):
        if data.get("status") == "PASS":
            result["passed_rules"].append(rule_id)
        else:
            result["violations"].append({
                "rule_id": rule_id,
                "message": data.get("message", ""),
            })

    result["rules_checked"] = len(results)
    result["status"] = "PASS" if ok else "FAIL"
    return result


# ---------------------------------------------------------------------------
# Check: Phase 3 contract artifact integrity
# ---------------------------------------------------------------------------


def _check_contract_artifacts(repo_root: Path) -> Dict[str, Any]:
    """Verify Phase 3 contract artifacts exist and hashes match the manifest.

    Checks:
      1. proof_registry_abi.json exists
      2. proof_registry_bytecode.json exists
      3. compiler_manifest.json exists
      4. proof_registry_spec.md exists
      5. ABI sha256 in manifest matches actual file
      6. Bytecode sha256 in manifest matches actual file
      7. ABI contains addProof, hasProof, ProofAdded
    """
    contracts_dir = repo_root / "24_meta_orchestration" / "contracts"
    abi_path = contracts_dir / "proof_registry_abi.json"
    bytecode_path = contracts_dir / "proof_registry_bytecode.json"
    manifest_path = contracts_dir / "compiler_manifest.json"
    spec_path = contracts_dir / "proof_registry_spec.md"

    result: Dict[str, Any] = {
        "check": "contract_artifact_integrity",
        "status": "UNKNOWN",
        "violations": [],
        "artifacts": {},
    }

    violations: List[Dict[str, str]] = []

    # Check file existence
    for label, path in [
        ("proof_registry_abi.json", abi_path),
        ("proof_registry_bytecode.json", bytecode_path),
        ("compiler_manifest.json", manifest_path),
        ("proof_registry_spec.md", spec_path),
    ]:
        if not path.is_file():
            violations.append({
                "rule_id": f"ARTIFACT_{label.upper().replace('.', '_').replace('-', '_')}_MISSING",
                "message": f"Required artifact missing: {label}",
            })
        else:
            result["artifacts"][label] = _file_sha256(path)

    if violations:
        result["violations"] = violations
        result["status"] = "FAIL"
        return result

    # Check hash integrity via compiler_manifest.json
    try:
        manifest: Dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        violations.append({
            "rule_id": "ARTIFACT_MANIFEST_PARSE_ERROR",
            "message": f"Cannot parse compiler_manifest.json: {exc}",
        })
        result["violations"] = violations
        result["status"] = "FAIL"
        return result

    # ABI hash
    recorded_abi_hash: Optional[str] = (
        manifest.get("artifacts", {}).get("abi", {}).get("sha256")
    )
    actual_abi_hash = _file_sha256(abi_path)
    if recorded_abi_hash and recorded_abi_hash != actual_abi_hash:
        violations.append({
            "rule_id": "ARTIFACT_ABI_HASH_DRIFT",
            "message": (
                f"ABI hash drift: manifest={recorded_abi_hash!r}, "
                f"actual={actual_abi_hash!r}"
            ),
        })

    # Bytecode hash
    recorded_bc_hash: Optional[str] = (
        manifest.get("artifacts", {}).get("bytecode", {}).get("sha256")
    )
    actual_bc_hash = _file_sha256(bytecode_path)
    if recorded_bc_hash and recorded_bc_hash != actual_bc_hash:
        violations.append({
            "rule_id": "ARTIFACT_BYTECODE_HASH_DRIFT",
            "message": (
                f"Bytecode hash drift: manifest={recorded_bc_hash!r}, "
                f"actual={actual_bc_hash!r}"
            ),
        })

    # ABI structure: addProof, hasProof, ProofAdded
    try:
        abi: list = json.loads(abi_path.read_text(encoding="utf-8"))
        fn_names = {e.get("name") for e in abi if e.get("type") == "function"}
        event_names = {e.get("name") for e in abi if e.get("type") == "event"}

        if "addProof" not in fn_names:
            violations.append({
                "rule_id": "ARTIFACT_ABI_MISSING_ADD_PROOF",
                "message": "ABI missing addProof function",
            })
        if "hasProof" not in fn_names:
            violations.append({
                "rule_id": "ARTIFACT_ABI_MISSING_HAS_PROOF",
                "message": "ABI missing hasProof function",
            })
        if "ProofAdded" not in event_names:
            violations.append({
                "rule_id": "ARTIFACT_ABI_MISSING_PROOF_ADDED_EVENT",
                "message": "ABI missing ProofAdded event",
            })
    except (json.JSONDecodeError, OSError) as exc:
        violations.append({
            "rule_id": "ARTIFACT_ABI_PARSE_ERROR",
            "message": f"Cannot parse proof_registry_abi.json: {exc}",
        })

    result["violations"] = violations
    result["status"] = "PASS" if not violations else "FAIL"
    return result


# ---------------------------------------------------------------------------
# Check: No .sol files in repository
# ---------------------------------------------------------------------------


def _load_sol_zone_policy(repo_root: Path) -> List[str]:
    """Load allowed Solidity zones from the canonical zone policy YAML.

    Falls back to a built-in list if the policy file cannot be read.
    """
    policy_path = repo_root / "23_compliance" / "policies" / "solidity_zone_policy.yaml"
    fallback_zones = [
        "03_core/contracts",
        "07_governance_legal/contracts",
        "16_codex/contracts",
        "18_data_layer/contracts",
        "19_adapters/contracts",
        "20_foundation/hardhat/contracts",
        "20_foundation/tokenomics/contracts",
        "20_foundation/shards/10_finanzen_banking/implementations/solidity/contracts",
        "23_compliance/contracts",
    ]
    if not policy_path.is_file():
        return fallback_zones
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
        zones = data.get("allowed_zones", fallback_zones)
        return [str(z) for z in zones]
    except Exception:
        # If yaml is unavailable or parse fails, use fallback
        return fallback_zones


def _check_no_sol_files(repo_root: Path) -> Dict[str, Any]:
    """Verify .sol files only exist inside allowed Solidity zones.

    Loads allowed zones from 23_compliance/policies/solidity_zone_policy.yaml.
    Files inside allowed zones are PASS; files outside are FAIL.

    Returns a check result dict with status PASS/FAIL.
    """
    result: Dict[str, Any] = {
        "check": "sol_zone_enforcement",
        "status": "UNKNOWN",
        "violations": [],
        "allowed_zones": [],
        "in_zone_files": [],
        "out_of_zone_files": [],
    }

    allowed_zones = _load_sol_zone_policy(repo_root)
    result["allowed_zones"] = allowed_zones

    sol_files = [
        p for p in repo_root.rglob("*.sol")
        if ".git" not in p.parts
    ]

    for sol_path in sorted(sol_files):
        rel = str(sol_path.relative_to(repo_root)).replace("\\", "/")
        in_zone = any(rel.startswith(zone + "/") or rel.startswith(zone + "\\") for zone in allowed_zones)
        if in_zone:
            result["in_zone_files"].append(rel)
        else:
            result["out_of_zone_files"].append(rel)
            result["violations"].append({
                "rule_id": "SOL_FILE_OUTSIDE_ZONE",
                "message": f"Found .sol file outside allowed zone: {rel}",
            })

    result["status"] = "PASS" if not result["violations"] else "FAIL"
    return result


# ---------------------------------------------------------------------------
# Build full report
# ---------------------------------------------------------------------------


def run_gate(
    repo_root: Path,
    check_sot: bool = True,
    check_artifacts: bool = True,
    check_no_sol: bool = True,
) -> Dict[str, Any]:
    """Run all enabled gate checks and return a structured report.

    Args:
        repo_root: Path to the SSID repository root.
        check_sot: Whether to run the SoT contract validation check.
        check_artifacts: Whether to verify Phase 3 contract artifact integrity.
        check_no_sol: Whether to verify no .sol files exist.

    Returns:
        Structured report dict with overall status, per-check results,
        violation list, and evidence hashes.
    """
    ts = _utc_now()
    checks: List[Dict[str, Any]] = []
    all_violations: List[Dict[str, str]] = []

    # Run enabled checks
    if check_sot:
        sot_result = _check_sot_contract(repo_root)
        checks.append(sot_result)
        all_violations.extend(sot_result.get("violations", []))

    if check_artifacts:
        artifact_result = _check_contract_artifacts(repo_root)
        checks.append(artifact_result)
        all_violations.extend(artifact_result.get("violations", []))

    if check_no_sol:
        sol_result = _check_no_sol_files(repo_root)
        checks.append(sol_result)
        all_violations.extend(sol_result.get("violations", []))

    overall = "PASS" if not all_violations else "FAIL"

    # Evidence hashes for key files
    evidence_files = [
        "03_core/validators/sot/sot_validator_core.py",
        "16_codex/contracts/sot/sot_contract.yaml",
        "24_meta_orchestration/contracts/proof_registry_abi.json",
        "24_meta_orchestration/contracts/proof_registry_bytecode.json",
        "24_meta_orchestration/contracts/compiler_manifest.json",
    ]
    artifacts_hashed = [
        {"path": p, "sha256": _file_sha256(repo_root / p)}
        for p in evidence_files
    ]

    report = {
        "gate": GATE_NAME,
        "version": GATE_VERSION,
        "timestamp_utc": ts,
        "repo_root": str(repo_root),
        "status": overall,
        "summary": {
            "total_checks": len(checks),
            "passed_checks": sum(1 for c in checks if c.get("status") == "PASS"),
            "failed_checks": sum(1 for c in checks if c.get("status") != "PASS"),
            "total_violations": len(all_violations),
        },
        "checks": checks,
        "violations": all_violations,
        "evidence": {
            "artifacts_hashed": artifacts_hashed,
        },
    }
    return report


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------


def _report_to_md(report: Dict[str, Any]) -> str:
    """Render the gate report as a markdown document."""
    lines = [
        f"# SoT Runtime Enforcement Gate Report\n",
        f"\nGate: `{report['gate']}` v{report['version']}\n",
        f"\nTimestamp: {report['timestamp_utc']}\n",
        f"\nStatus: **{report['status']}**\n",
        f"\n## Summary\n",
        f"\n- Total checks: {report['summary']['total_checks']}\n",
        f"- Passed: {report['summary']['passed_checks']}\n",
        f"- Failed: {report['summary']['failed_checks']}\n",
        f"- Total violations: {report['summary']['total_violations']}\n",
    ]

    if report["violations"]:
        lines.append("\n## Violations\n")
        for v in report["violations"]:
            lines.append(f"- **{v['rule_id']}**: {v['message']}\n")
    else:
        lines.append("\n## Violations\n\nNone.\n")

    lines.append("\n## Checks\n")
    for check in report["checks"]:
        status_icon = "PASS" if check.get("status") == "PASS" else "FAIL"
        lines.append(f"\n### {check['check']} — {status_icon}\n")
        v_count = len(check.get("violations", []))
        if v_count:
            lines.append(f"Violations: {v_count}\n")
            for v in check.get("violations", []):
                lines.append(f"- `{v['rule_id']}`: {v['message']}\n")

    lines.append("\n## Evidence Hashes\n")
    for a in report["evidence"]["artifacts_hashed"]:
        lines.append(f"- `{a['path']}`: `{a['sha256'][:16]}...`\n")

    return "".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """Parse CLI arguments and run the unified enforcement gate.

    Exit codes:
        0 — PASS: no violations
        1 — FAIL: violations detected or --fail-on-drift triggered
    """
    parser = argparse.ArgumentParser(
        prog=GATE_NAME,
        description=(
            "Unified SoT Runtime Enforcement Gate — "
            "SoT validation + artifact integrity + .sol prohibition. "
            "Use --fail-on-drift to enforce all checks in CI."
        ),
    )
    parser.add_argument(
        "--repo-root",
        type=str,
        default=str(_REPO_ROOT),
        help="Path to SSID repo root (default: auto-detect)",
    )
    parser.add_argument(
        "--fail-on-drift",
        action="store_true",
        help="Exit 1 if any drift or violation is detected (recommended for CI)",
    )
    parser.add_argument(
        "--write-reports",
        action="store_true",
        help="Write JSON + MD reports to 02_audit_logging/reports/",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Output JSON report to stdout only (for piping)",
    )
    parser.add_argument(
        "--no-check-sot",
        action="store_true",
        help="Skip SoT contract validation check",
    )
    parser.add_argument(
        "--no-check-artifacts",
        action="store_true",
        help="Skip Phase 3 contract artifact integrity check",
    )
    parser.add_argument(
        "--no-check-sol",
        action="store_true",
        help="Skip .sol file prohibition check",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root)
    report = run_gate(
        repo_root=repo_root,
        check_sot=not args.no_check_sot,
        check_artifacts=not args.no_check_artifacts,
        check_no_sol=not args.no_check_sol,
    )

    if args.json_only:
        print(json.dumps(report, indent=2))
        return 0 if report["status"] == "PASS" else 1

    # Write reports to disk if requested
    if args.write_reports:
        _REPORT_DIR.mkdir(parents=True, exist_ok=True)
        json_path = _REPORT_DIR / f"{GATE_NAME}_report.json"
        md_path = _REPORT_DIR / f"{GATE_NAME}_report.md"
        json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        md_path.write_text(_report_to_md(report), encoding="utf-8")
        print(f"REPORT: {json_path.relative_to(repo_root)}")
        print(f"REPORT: {md_path.relative_to(repo_root)}")

    # Always print summary
    summary = report["summary"]
    print(
        f"{GATE_NAME.upper()}: {report['status']} "
        f"({summary['passed_checks']}/{summary['total_checks']} checks passed, "
        f"{summary['total_violations']} violations)"
    )

    if report["violations"]:
        for v in report["violations"]:
            print(f"  VIOLATION: {v['rule_id']}: {v['message']}")

    # Determine exit code
    has_violations = report["status"] != "PASS"
    if args.fail_on_drift and has_violations:
        print("GATE: --fail-on-drift active, exiting 1")
        return 1

    return 0 if not has_violations else 1


if __name__ == "__main__":
    raise SystemExit(main())
