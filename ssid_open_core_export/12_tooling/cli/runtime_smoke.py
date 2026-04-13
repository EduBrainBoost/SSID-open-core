#!/usr/bin/env python3
"""CLI entry point for runtime smoke checks."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "12_tooling" / "ops" / "runtime_smoke"))

import runtime_smoke_lib as rslib  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SSID Runtime Smoke Check")
    parser.add_argument("--config", required=True, help="Path to targets JSON config file")
    parser.add_argument("--write-evidence", action="store_true", help="Write evidence JSON to canonical path")
    parser.add_argument("--evidence-dir", default=None, help="Override base directory for evidence output")
    args = parser.parse_args(argv)

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"ERROR: Config file not found: {config_path}", file=sys.stderr)
        return 1

    config = json.loads(config_path.read_text(encoding="utf-8"))
    payload = rslib.run_all(config)
    passed = rslib.evaluate_results(payload)

    # Print summary
    print()
    print(f"{'SERVICE':<25} {'STATUS':<8} {'HTTP':<6} {'ms':<6} NOTE")
    print("-" * 70)
    for t in payload["targets"]:
        http_s = str(t.get("http_status") or "")
        ms_s = str(t.get("elapsed_ms", ""))
        note = t.get("skip_reason") or t.get("error") or ""
        print(f"{t['name']:<25} {t['status']:<8} {http_s:<6} {ms_s:<6} {note}")
    print()
    print(f"RESULT: {'PASS' if passed else 'FAIL'}")

    if args.write_evidence:
        base = Path(args.evidence_dir) if args.evidence_dir else _REPO_ROOT
        evidence_path = rslib.write_evidence(payload, base)
        print(f"Evidence: {evidence_path}")

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
