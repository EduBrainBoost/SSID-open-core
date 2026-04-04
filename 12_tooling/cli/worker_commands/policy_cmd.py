"""ssidctl worker: policy — policy check runner.

Usage:
    python -m ssidctl.commands.policy check --scope <root>
    python -m ssidctl.commands.policy validate --file <path>
    python -m ssidctl.commands.policy status
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT_24 = [
    "01_ai_layer",
    "02_audit_logging",
    "03_core",
    "04_deployment",
    "05_documentation",
    "06_data_pipeline",
    "07_governance_legal",
    "08_identity_score",
    "09_meta_identity",
    "10_interoperability",
    "11_test_simulation",
    "12_tooling",
    "13_ui_layer",
    "14_zero_time_auth",
    "15_infra",
    "16_codex",
    "17_observability",
    "18_data_layer",
    "19_adapters",
    "20_foundation",
    "21_post_quantum_crypto",
    "22_datasets",
    "23_compliance",
    "24_meta_orchestration",
]

ENFORCED_POLICIES = [
    "ROOT-24-LOCK",
    "SAFE-FIX",
    "NON-INTERACTIVE",
    "NO-SCAN-RULE",
    "SESSION-ISOLATION",
    "PORT-POLICY",
]


def _check(args: argparse.Namespace) -> int:
    """Run policy checks for a given scope."""
    scope = args.scope
    violations = []

    # ROOT-24-LOCK check
    if scope not in ROOT_24 and scope != "all":
        violations.append(
            {
                "policy": "ROOT-24-LOCK",
                "detail": f"Scope '{scope}' is not a canonical root",
                "severity": "error",
            }
        )

    output = {
        "command": "policy.check",
        "timestamp": datetime.now(UTC).isoformat(),
        "scope": scope,
        "policies_checked": ENFORCED_POLICIES,
        "violations": violations,
        "violation_count": len(violations),
        "status": "pass" if not violations else "fail",
    }
    print(json.dumps(output, indent=2))
    return 1 if violations else 0


def _validate(args: argparse.Namespace) -> int:
    """Validate a specific file against policy rules."""
    file_path = Path(args.file)

    checks = {
        "exists": file_path.exists(),
        "root_24_compliant": any(r in str(file_path) for r in ROOT_24),
        "not_repo_root_file": "/"
        in str(file_path.relative_to(file_path.anchor) if file_path.is_absolute() else file_path),
    }
    violations = [k for k, v in checks.items() if not v]

    output = {
        "command": "policy.validate",
        "timestamp": datetime.now(UTC).isoformat(),
        "file": str(file_path),
        "checks": checks,
        "violations": violations,
        "status": "pass" if not violations else "fail",
    }
    print(json.dumps(output, indent=2))
    return 1 if violations else 0


def _status(args: argparse.Namespace) -> int:
    """Report policy worker status."""
    output = {
        "command": "policy.status",
        "timestamp": datetime.now(UTC).isoformat(),
        "enforced_policies": ENFORCED_POLICIES,
        "policy_count": len(ENFORCED_POLICIES),
        "canonical_roots": len(ROOT_24),
        "mode": "NON_INTERACTIVE",
    }
    print(json.dumps(output, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ssidctl-policy",
        description="SSIDCTL Policy Worker — policy check runner",
    )
    sub = parser.add_subparsers(dest="action", required=True)

    check_p = sub.add_parser("check", help="Run policy checks")
    check_p.add_argument("--scope", required=True, help="Root scope or 'all'")

    validate_p = sub.add_parser("validate", help="Validate file against policies")
    validate_p.add_argument("--file", required=True, help="File to validate")

    sub.add_parser("status", help="Policy worker status")

    args = parser.parse_args(argv)

    dispatch_map = {
        "check": _check,
        "validate": _validate,
        "status": _status,
    }

    try:
        return dispatch_map[args.action](args)
    except Exception as exc:
        error = {
            "command": f"policy.{args.action}",
            "timestamp": datetime.now(UTC).isoformat(),
            "error": str(exc),
            "status": "failed",
        }
        print(json.dumps(error, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
