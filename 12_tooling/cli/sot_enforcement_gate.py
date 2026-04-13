#!/usr/bin/env python3
"""
SoT Runtime Enforcement Gate — unified enforcement flow.
Combines sot_validator_core.py + sot_contract.yaml + sot_policy.rego (optional).
Produces: JSON report, MD report, registry event, PASS/FAIL exit code.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

REPO_ROOT = Path(__file__).resolve().parents[2]
CORE_PATH = REPO_ROOT / "03_core" / "validators" / "sot" / "sot_validator_core.py"
CONTRACT_PATH = REPO_ROOT / "16_codex" / "contracts" / "sot" / "sot_contract.yaml"
POLICY_PATH = REPO_ROOT / "23_compliance" / "policies" / "sot" / "sot_policy.rego"
REPORT_DIR = REPO_ROOT / "02_audit_logging" / "reports"
REGISTRY_DIR = REPO_ROOT / "24_meta_orchestration" / "registry"


def _load_core():
    spec = importlib.util.spec_from_file_location("sot_core", str(CORE_PATH))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {CORE_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_contract(repo_root: Path) -> Dict[str, Any]:
    """Load sot_contract.yaml and return parsed dict."""
    contract_path = repo_root / "16_codex" / "contracts" / "sot" / "sot_contract.yaml"
    if not contract_path.is_file():
        return {"version": "unknown", "rule_count": 0}
    try:
        import yaml
        return yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    except ImportError:
        text = contract_path.read_text(encoding="utf-8")
        version = "unknown"
        rule_count = 0
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("version:"):
                version = stripped.split(":", 1)[1].strip()
            if stripped.startswith("- id:"):
                rule_count += 1
        return {"version": version, "rule_count": rule_count}


def _check_policy_rego(repo_root: Path) -> Dict[str, Any]:
    """Check that sot_policy.rego exists and is non-empty."""
    policy_path = repo_root / "23_compliance" / "policies" / "sot" / "sot_policy.rego"
    rel = "23_compliance/policies/sot/sot_policy.rego"
    if not policy_path.is_file():
        return {"status": "MISSING", "path": rel}
    content = policy_path.read_text(encoding="utf-8", errors="replace")
    return {
        "status": "PRESENT",
        "path": rel,
        "sha256": hashlib.sha256(content.encode()).hexdigest(),
        "line_count": len(content.splitlines()),
    }


def _file_hash(path: Path) -> str:
    if not path.is_file():
        return "MISSING"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_enforcement(repo_root: Path) -> Dict[str, Any]:
    """Run the full enforcement gate and return structured report."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 1. Load and run validator core
    mod = _load_core()
    validator = mod.SoTValidatorCore(str(repo_root))
    results = validator.validate_all()
    ok, failed = validator.evaluate_priorities(results)

    # 2. Load contract metadata
    contract_path = repo_root / "16_codex" / "contracts" / "sot" / "sot_contract.yaml"
    core_path = repo_root / "03_core" / "validators" / "sot" / "sot_validator_core.py"
    contract = _load_contract(repo_root)

    # 3. Check policy rego
    policy = _check_policy_rego(repo_root)

    # 4. Build report
    violations = []
    passed_rules = []
    for rule_id, data in sorted(results.items()):
        entry = {"rule_id": rule_id, "message": data.get("message", "")}
        if data.get("status") == "PASS":
            passed_rules.append(entry)
        else:
            violations.append(entry)

    report = {
        "gate": "sot_runtime_enforcement",
        "version": "1.0.0",
        "timestamp_utc": ts,
        "status": "PASS" if ok else "FAIL",
        "contract": {
            "path": "16_codex/contracts/sot/sot_contract.yaml",
            "version": contract.get("version", "unknown"),
            "sha256": _file_hash(contract_path),
        },
        "validator": {
            "path": "03_core/validators/sot/sot_validator_core.py",
            "sha256": _file_hash(core_path),
            "rules_checked": len(results),
        },
        "policy": policy,
        "summary": {
            "total_rules": len(results),
            "passed": len(passed_rules),
            "failed": len(violations),
        },
        "violations": violations,
        "passed_rules": [r["rule_id"] for r in passed_rules],
        "evidence": {
            "artifacts_hashed": [
                {"path": p, "sha256": _file_hash(repo_root / p)}
                for p in mod.SoTValidatorCore.CANONICAL_SOT_ARTIFACTS
            ],
        },
    }
    return report


def _report_to_md(report: Dict[str, Any]) -> str:
    """Render enforcement report as markdown."""
    lines = [
        "# SoT Runtime Enforcement Report\n",
        f"\nTimestamp: {report['timestamp_utc']}\n",
        f"Status: **{report['status']}**\n",
        f"Contract: {report['contract']['path']} v{report['contract']['version']}\n",
        f"Rules checked: {report['summary']['total_rules']}\n",
        f"Passed: {report['summary']['passed']}\n",
        f"Failed: {report['summary']['failed']}\n",
    ]
    if report["violations"]:
        lines.append("\n## Violations\n")
        for v in report["violations"]:
            lines.append(f"- **{v['rule_id']}**: {v['message']}\n")
    if report["passed_rules"]:
        lines.append("\n## Passed Rules\n")
        for rid in report["passed_rules"]:
            lines.append(f"- {rid}\n")
    lines.append("\n## Evidence Hashes\n")
    for a in report["evidence"]["artifacts_hashed"]:
        lines.append(f"- `{a['path']}`: `{a['sha256'][:16]}...`\n")
    return "".join(lines)


def _write_registry_event(report: Dict[str, Any], repo_root: Path) -> Path:
    """Write registry event for this enforcement run."""
    event = {
        "event_type": "sot_enforcement_gate",
        "timestamp_utc": report["timestamp_utc"],
        "status": report["status"],
        "rules_checked": report["summary"]["total_rules"],
        "violations": report["summary"]["failed"],
        "contract_version": report["contract"]["version"],
        "contract_sha256": report["contract"]["sha256"],
        "validator_sha256": report["validator"]["sha256"],
    }
    ts_slug = report["timestamp_utc"].replace(":", "").replace("-", "")
    registry_dir = repo_root / "24_meta_orchestration" / "registry"
    event_path = registry_dir / f"sot_enforcement_event_{ts_slug}.json"
    event_path.parent.mkdir(parents=True, exist_ok=True)
    event_path.write_text(json.dumps(event, indent=2), encoding="utf-8")
    return event_path


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="sot_enforcement_gate",
        description="SoT Runtime Enforcement Gate — unified PASS/FAIL check",
    )
    parser.add_argument(
        "--repo-root", type=str, default=str(REPO_ROOT),
        help="Path to SSID repo root (default: auto-detect)",
    )
    parser.add_argument(
        "--write-reports", action="store_true",
        help="Write JSON + MD reports to 02_audit_logging/reports/",
    )
    parser.add_argument(
        "--write-registry", action="store_true",
        help="Write registry event to 24_meta_orchestration/registry/",
    )
    parser.add_argument(
        "--json-only", action="store_true",
        help="Output JSON report to stdout (for piping)",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root)
    report = run_enforcement(repo_root)

    if args.json_only:
        print(json.dumps(report, indent=2))
        return 0 if report["status"] == "PASS" else 1

    # Write reports if requested
    if args.write_reports:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        json_path = REPORT_DIR / "sot_runtime_enforcement_report.json"
        md_path = REPORT_DIR / "sot_runtime_enforcement_report.md"
        json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        md_path.write_text(_report_to_md(report), encoding="utf-8")
        print(f"REPORT: {json_path.relative_to(repo_root)}")
        print(f"REPORT: {md_path.relative_to(repo_root)}")

    if args.write_registry:
        event_path = _write_registry_event(report, repo_root)
        print(f"REGISTRY: {event_path.relative_to(repo_root)}")

    # Always print summary
    print(f"SOT_ENFORCEMENT: {report['status']} "
          f"({report['summary']['passed']}/{report['summary']['total_rules']} passed)")

    if report["violations"]:
        for v in report["violations"]:
            print(f"  FAIL: {v['rule_id']}: {v['message']}")

    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
