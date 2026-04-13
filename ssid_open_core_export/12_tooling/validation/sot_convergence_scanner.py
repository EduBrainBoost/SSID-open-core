#!/usr/bin/env python3
"""SoT Convergence Scanner -- read-only drift detection against sot_contract.yaml.

Parses the canonical SoT contract, inspects filesystem and registry bindings,
and classifies drift into well-defined categories. Never modifies any file.

Usage:
    python sot_convergence_scanner.py \\
        --contract 16_codex/contracts/sot/sot_contract.yaml \\
        --repo-root /path/to/SSID \\
        --repo-role canonical
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    sys.exit("ERROR: PyYAML is required. Install via: pip install pyyaml")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DRIFT_CLASSES = frozenset(
    {
        "missing_required_artifact",
        "path_violation",
        "registry_missing",
        "policy_missing",
        "test_missing",
        "enforcement_gap",
        "export_violation",
        "protected_scope_attempt",
        "stale_derivative_binding",
    }
)

VALID_REPO_ROLES = ("canonical", "derivative", "orchestration")

# Well-known paths relative to repo root used for heuristic checks.
_REGISTRY_PATH = Path("24_meta_orchestration/registry/sot_registry.json")
_STRUCTURE_SPEC_PATH = Path("24_meta_orchestration/registry/structure_spec.json")
_POLICY_DIR = Path("23_compliance/policies/sot")
_TEST_DIR = Path("11_test_simulation/tests_compliance")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sha256_file(path: Path) -> str:
    """Return hex SHA-256 of *path*."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_yaml(path: Path) -> Any:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _load_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _exists(repo_root: Path, rel: str) -> bool:
    """Check whether a relative path exists under *repo_root*."""
    return (repo_root / rel).exists()


# ---------------------------------------------------------------------------
# Contract parsing
# ---------------------------------------------------------------------------


def parse_contract(contract_path: Path) -> dict[str, Any]:
    """Parse sot_contract.yaml and return structured data.

    Returns dict with keys: version, rules (list[dict]), agent_stack, rule_count.
    rule_count is derived dynamically from the parsed rules list.
    """
    data = _load_yaml(contract_path)
    if not isinstance(data, dict):
        raise ValueError(f"Contract root must be a mapping, got {type(data).__name__}")

    rules: list[dict[str, Any]] = data.get("rules", [])
    return {
        "version": data.get("version", "unknown"),
        "rules": rules,
        "rule_count": len(rules),
        "agent_stack": data.get("agent_stack", []),
    }


# ---------------------------------------------------------------------------
# Registry inspection
# ---------------------------------------------------------------------------


def load_registry(repo_root: Path) -> dict[str, Any] | None:
    """Load sot_registry.json if it exists, else return None."""
    p = repo_root / _REGISTRY_PATH
    if not p.is_file():
        return None
    return _load_json(p)


def load_structure_spec(repo_root: Path) -> dict[str, Any] | None:
    """Load structure_spec.json if it exists, else return None."""
    p = repo_root / _STRUCTURE_SPEC_PATH
    if not p.is_file():
        return None
    return _load_json(p)


# ---------------------------------------------------------------------------
# Expected-artifact computation
# ---------------------------------------------------------------------------


def _expected_artifacts_from_registry(
    registry: dict[str, Any] | None,
) -> list[str]:
    """Return sorted list of expected artifact paths from registry."""
    if registry is None:
        return []
    artifacts = registry.get("roots", {}).get("sot_artifacts", [])
    return sorted(a["path"] for a in artifacts if "path" in a)


def _expected_must_paths(spec: dict[str, Any] | None) -> list[str]:
    """Return sorted MUST paths from structure_spec."""
    if spec is None:
        return []
    return sorted(spec.get("paths", {}).get("must", []))


# ---------------------------------------------------------------------------
# Drift classification
# ---------------------------------------------------------------------------


def _classify_drift(
    repo_root: Path,
    contract: dict[str, Any],
    registry: dict[str, Any] | None,
    spec: dict[str, Any] | None,
    repo_role: str,
) -> tuple[
    list[str],  # expected_artifacts
    list[str],  # actual_artifacts
    list[str],  # missing_artifacts
    list[dict[str, Any]],  # drift_findings
    list[dict[str, str]],  # blocked_operations
]:
    """Run all drift checks and return aggregated results."""
    drift_findings: list[dict[str, Any]] = []
    blocked_operations: list[dict[str, str]] = []

    # --- 1. Registry artifact checks ---
    expected = _expected_artifacts_from_registry(registry)
    actual = [p for p in expected if _exists(repo_root, p)]
    missing = sorted(set(expected) - set(actual))

    for m in missing:
        drift_findings.append(
            {
                "class": "missing_required_artifact",
                "path": m,
                "severity": "high",
                "detail": f"Registry-listed artifact not found on disk: {m}",
            }
        )

    # --- 2. MUST-path checks from structure_spec ---
    must_paths = _expected_must_paths(spec)
    for mp in must_paths:
        if not _exists(repo_root, mp):
            drift_findings.append(
                {
                    "class": "path_violation",
                    "path": mp,
                    "severity": "high",
                    "detail": f"MUST path missing: {mp}",
                }
            )

    # --- 3. Registry existence ---
    if registry is None:
        drift_findings.append(
            {
                "class": "registry_missing",
                "path": str(_REGISTRY_PATH),
                "severity": "critical",
                "detail": "sot_registry.json not found",
            }
        )

    # --- 4. Policy directory check ---
    policy_dir = repo_root / _POLICY_DIR
    if not policy_dir.is_dir():
        drift_findings.append(
            {
                "class": "policy_missing",
                "path": str(_POLICY_DIR),
                "severity": "high",
                "detail": "SoT policy directory missing",
            }
        )
    else:
        rego_files = list(policy_dir.glob("*.rego"))
        if not rego_files:
            drift_findings.append(
                {
                    "class": "policy_missing",
                    "path": str(_POLICY_DIR / "*.rego"),
                    "severity": "high",
                    "detail": "No .rego policy files in SoT policy directory",
                }
            )

    # --- 5. Test existence ---
    test_dir = repo_root / _TEST_DIR
    if not test_dir.is_dir():
        drift_findings.append(
            {
                "class": "test_missing",
                "path": str(_TEST_DIR),
                "severity": "high",
                "detail": "Compliance test directory missing",
            }
        )
    else:
        sot_tests = list(test_dir.glob("test_sot_*.py"))
        if not sot_tests:
            drift_findings.append(
                {
                    "class": "test_missing",
                    "path": str(_TEST_DIR / "test_sot_*.py"),
                    "severity": "high",
                    "detail": "No SoT test files found",
                }
            )

    # --- 6. Enforcement gap: rules without hard_fail ---
    for rule in contract.get("rules", []):
        if rule.get("mode") != "hard_fail":
            drift_findings.append(
                {
                    "class": "enforcement_gap",
                    "path": f"rule:{rule.get('id', '?')}",
                    "severity": "medium",
                    "detail": (f"Rule {rule.get('id')} mode is '{rule.get('mode')}', expected 'hard_fail'"),
                }
            )

    # --- 7. Forbidden-zone violation (structure_spec.forbidden_zones) ---
    forbidden = spec.get("forbidden_zones", []) if spec else []
    for fz in forbidden:
        fz_path = repo_root / fz
        if fz_path.exists() and any(fz_path.iterdir()) if fz_path.is_dir() else fz_path.exists():
            drift_findings.append(
                {
                    "class": "protected_scope_attempt",
                    "path": fz,
                    "severity": "critical",
                    "detail": f"Forbidden zone contains content: {fz}",
                }
            )

    # --- 8. Export-readiness (derivative/orchestration role checks) ---
    if repo_role == "derivative":
        # Derivative repos must NOT contain the canonical contract itself
        if _exists(repo_root, "16_codex/contracts/sot/sot_contract.yaml"):
            drift_findings.append(
                {
                    "class": "export_violation",
                    "path": "16_codex/contracts/sot/sot_contract.yaml",
                    "severity": "critical",
                    "detail": "Derivative repo must not contain canonical contract",
                }
            )
            blocked_operations.append(
                {
                    "operation": "export",
                    "reason": "Canonical contract present in derivative repo",
                }
            )

    # --- 9. Stale derivative binding: registry hash mismatches ---
    if registry is not None:
        for artifact in registry.get("roots", {}).get("sot_artifacts", []):
            art_path = repo_root / artifact["path"]
            if art_path.is_file() and "hash_sha256" in artifact:
                actual_hash = _sha256_file(art_path)
                if actual_hash != artifact["hash_sha256"]:
                    drift_findings.append(
                        {
                            "class": "stale_derivative_binding",
                            "path": artifact["path"],
                            "severity": "high",
                            "detail": (
                                f"Hash mismatch for {artifact['path']}: "
                                f"registry={artifact['hash_sha256'][:16]}... "
                                f"actual={actual_hash[:16]}..."
                            ),
                        }
                    )

    return expected, actual, missing, drift_findings, blocked_operations


# ---------------------------------------------------------------------------
# Main scan
# ---------------------------------------------------------------------------


def scan(
    canonical_contract_path: str,
    target_repo_root: str,
    repo_role: str,
) -> dict[str, Any]:
    """Execute the convergence scan and return the result dict.

    Parameters
    ----------
    canonical_contract_path:
        Path to sot_contract.yaml (absolute or relative to *target_repo_root*).
    target_repo_root:
        Root of the repository to scan.
    repo_role:
        One of ``canonical``, ``derivative``, ``orchestration``.

    Returns
    -------
    dict with all mandatory output fields.
    """
    if repo_role not in VALID_REPO_ROLES:
        raise ValueError(f"repo_role must be one of {VALID_REPO_ROLES}, got '{repo_role}'")

    repo_root = Path(target_repo_root).resolve()
    contract_path = Path(canonical_contract_path)
    if not contract_path.is_absolute():
        contract_path = repo_root / contract_path

    if not contract_path.is_file():
        raise FileNotFoundError(f"Contract not found: {contract_path}")

    contract = parse_contract(contract_path)
    contract_sha = _sha256_file(contract_path)

    registry = load_registry(repo_root)
    spec = load_structure_spec(repo_root)

    expected, actual, missing, findings, blocked = _classify_drift(repo_root, contract, registry, spec, repo_role)

    export_ready = len(blocked) == 0 and not any(f["class"] == "export_violation" for f in findings)

    status = "PASS" if len(findings) == 0 else "FAIL"

    return {
        "repo_name": repo_root.name,
        "repo_role": repo_role,
        "scan_time_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "contract_path": str(contract_path.relative_to(repo_root)),
        "contract_version": contract["version"],
        "contract_sha256": contract_sha,
        "rule_count": contract["rule_count"],
        "expected_artifacts": expected,
        "actual_artifacts": actual,
        "missing_artifacts": missing,
        "drift_findings": findings,
        "blocked_operations": blocked,
        "export_ready": export_ready,
        "status": status,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="SoT Convergence Scanner -- read-only drift detection",
    )
    parser.add_argument(
        "--contract",
        required=True,
        help="Path to sot_contract.yaml (absolute or relative to --repo-root)",
    )
    parser.add_argument(
        "--repo-root",
        required=True,
        help="Root of the target repository",
    )
    parser.add_argument(
        "--repo-role",
        required=True,
        choices=VALID_REPO_ROLES,
        help="Role of the repository (canonical | derivative | orchestration)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Output file path (default: stdout)",
    )
    args = parser.parse_args(argv)

    result = scan(
        canonical_contract_path=args.contract,
        target_repo_root=args.repo_root,
        repo_role=args.repo_role,
    )

    output_json = json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output_json + "\n", encoding="utf-8")
        print(f"Scan result written to {out_path}", file=sys.stderr)
    else:
        print(output_json)

    sys.exit(0 if result["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
