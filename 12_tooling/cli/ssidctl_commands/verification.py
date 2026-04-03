#!/usr/bin/env python3
"""ssidctl verification -- Run verification checks against the repository."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CANONICAL_ROOTS: list[str] = [
    "01_ai_layer", "02_audit_logging", "03_core", "04_deployment",
    "05_documentation", "06_data_pipeline", "07_governance_legal",
    "08_identity_score", "09_meta_identity", "10_interoperability",
    "11_test_simulation", "12_tooling", "13_ui_layer", "14_zero_time_auth",
    "15_infra", "16_codex", "17_observability", "18_data_layer",
    "19_adapters", "20_foundation", "21_post_quantum_crypto", "22_datasets",
    "23_compliance", "24_meta_orchestration",
]


def build_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """Build and return the argument parser for verification."""
    if subparsers is not None:
        parser = subparsers.add_parser("verification", help="Run verification checks")
    else:
        parser = argparse.ArgumentParser(prog="ssidctl verification", description=__doc__)
    parser.add_argument("--root", type=str, default=".", help="Repository root path")
    parser.add_argument("--check", choices=["roots", "manifests", "all"], default="all",
                        help="Which checks to run (default: all)")
    parser.add_argument("--json", dest="json_output", action="store_true", help="Output in JSON format")
    parser.set_defaults(func=run)
    return parser


def _check_root24(repo_root: Path) -> dict[str, object]:
    """Verify ROOT-24-LOCK compliance."""
    present: list[str] = []
    missing: list[str] = []
    for root_name in CANONICAL_ROOTS:
        if (repo_root / root_name).is_dir():
            present.append(root_name)
        else:
            missing.append(root_name)

    extra: list[str] = []
    for entry in sorted(repo_root.iterdir()):
        if entry.is_dir() and entry.name not in CANONICAL_ROOTS and not entry.name.startswith("."):
            extra.append(entry.name)

    return {
        "check": "root-24-lock",
        "present": len(present),
        "missing": missing,
        "extra_dirs": extra,
        "pass": len(missing) == 0 and len(extra) == 0,
    }


def _check_manifests(repo_root: Path) -> dict[str, object]:
    """Check for manifest files in roots."""
    found: list[str] = []
    missing_manifest: list[str] = []
    for root_name in CANONICAL_ROOTS:
        root_dir = repo_root / root_name
        if root_dir.is_dir():
            has_manifest = any(
                (root_dir / m).exists()
                for m in ("manifest.yaml", "manifest.json", "module.yaml")
            )
            if has_manifest:
                found.append(root_name)
            else:
                missing_manifest.append(root_name)
    return {
        "check": "manifests",
        "found": len(found),
        "missing": missing_manifest,
        "pass": len(missing_manifest) == 0,
    }


def run(args: argparse.Namespace) -> int:
    """Execute verification command."""
    repo_root = Path(args.root).resolve()
    checks: list[dict[str, object]] = []

    if args.check in ("roots", "all"):
        checks.append(_check_root24(repo_root))
    if args.check in ("manifests", "all"):
        checks.append(_check_manifests(repo_root))

    all_pass = all(c.get("pass", False) for c in checks)
    result: dict[str, object] = {
        "command": "verification",
        "root": str(repo_root),
        "checks": checks,
        "overall": "PASS" if all_pass else "FAIL",
    }

    if args.json_output:
        print(json.dumps(result, indent=2))
    else:
        print("Verification Report")
        print(f"  Root:    {repo_root}")
        for c in checks:
            status = "PASS" if c.get("pass") else "FAIL"
            print(f"  [{status}] {c['check']}")
            if c.get("missing"):
                for m in c["missing"]:  # type: ignore[union-attr]
                    print(f"         missing: {m}")
        print(f"  Overall: {result['overall']}")
    return 0


def main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()
    sys.exit(run(args))


if __name__ == "__main__":
    main()
