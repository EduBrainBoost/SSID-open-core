#!/usr/bin/env python3
"""run_structure_gates.py -- Runs all three structure validation gates.

Gates:
  1. Root-24 Lock: Exactly 24 canonical roots exist.
  2. Shard-16 Matrix: Each root has 16 shards with chart.yaml + manifest.yaml.
  3. SoT Validator: python 12_tooling/cli/sot_validator.py --verify-all.

Exit 0 only if all three PASS.
"""

import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]

CANONICAL_ROOTS = [
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


def gate_root24() -> bool:
    """Gate 1: Exactly 24 canonical roots exist."""
    for root in CANONICAL_ROOTS:
        if not (REPO / root).is_dir():
            print(f"FAIL root24: missing {root}")
            return False
    return True


def gate_shard16() -> bool:
    """Gate 2: Each root has shards/01_*..16_* with chart.yaml + manifest."""
    ok = True
    for root in CANONICAL_ROOTS:
        shards_dir = REPO / root / "shards"
        if not shards_dir.is_dir():
            print(f"FAIL shard16: {root}/shards/ missing")
            ok = False
            continue
        shard_dirs = sorted(d for d in shards_dir.iterdir() if d.is_dir() and d.name[:2].isdigit())
        if len(shard_dirs) != 16:
            print(f"FAIL shard16: {root} has {len(shard_dirs)} shards, expected 16")
            ok = False
        for sd in shard_dirs:
            if not (sd / "chart.yaml").is_file():
                print(f"FAIL shard16: {sd}/chart.yaml missing")
                ok = False
            if not (sd / "implementations" / "python" / "manifest.yaml").is_file():
                print(f"FAIL shard16: {sd}/implementations/python/manifest.yaml missing")
                ok = False
    return ok


def gate_sot_validator() -> bool:
    """Gate 3: sot_validator.py --verify-all returns 0."""
    result = subprocess.run(
        [sys.executable, str(REPO / "12_tooling" / "cli" / "sot_validator.py"), "--verify-all"],
        capture_output=True,
        text=True,
        cwd=str(REPO),
    )
    if result.returncode != 0:
        print(f"FAIL sot_validator: {result.stdout.strip()} {result.stderr.strip()}")
        return False
    return True


def main() -> int:
    results = []
    for name, fn in [("root24", gate_root24), ("shard16", gate_shard16), ("sot_validator", gate_sot_validator)]:
        passed = fn()
        tag = "PASS" if passed else "FAIL"
        print(f"Gate {name}: {tag}")
        results.append(passed)
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
