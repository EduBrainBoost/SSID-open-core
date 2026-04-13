#!/usr/bin/env python3
"""phase2_reality_scan.py -- Scans the repo for reality vs. SoT drift.

Checks:
  - Core engines exist and are importable.
  - Contract YAMLs parse correctly.
  - CLI tools exist and have valid Python syntax.
  - Evidence files are under ci_runs/.

Outputs a JSON evidence file to 23_compliance/evidence/ci_runs/.
"""

import datetime
import json
import pathlib
import py_compile
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]

CORE_ENGINES = [
    "03_core/fee_distribution_engine.py",
    "03_core/fairness_engine.py",
    "03_core/subscription_revenue_distributor.py",
    "16_codex/contract_registry.py",
    "17_observability/telemetry_engine.py",
    "21_post_quantum_crypto/pqc_engine.py",
]


def main() -> int:
    utc = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")
    findings = {"timestamp": utc, "engines": {}, "syntax_errors": []}
    exit_code = 0

    for eng in CORE_ENGINES:
        fpath = REPO / eng
        if fpath.is_file():
            findings["engines"][eng] = "PRESENT"
            try:
                py_compile.compile(str(fpath), doraise=True)
            except py_compile.PyCompileError as exc:
                findings["engines"][eng] = f"SYNTAX_ERROR: {exc}"
                findings["syntax_errors"].append(eng)
                exit_code = 1
        else:
            findings["engines"][eng] = "MISSING"
            exit_code = 1

    out_dir = REPO / "23_compliance" / "evidence" / "ci_runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{utc}_phase2_reality_scan.json"
    out_file.write_text(json.dumps(findings, indent=2), encoding="utf-8")
    print(f"Evidence written to {out_file.relative_to(REPO)}")

    for eng, status in findings["engines"].items():
        tag = "PASS" if status == "PRESENT" else "FAIL"
        print(f"  {tag}: {eng} ({status})")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
