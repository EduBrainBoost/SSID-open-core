#!/usr/bin/env python3
"""
AR-05: Shard Completion Gate — 24x16=384 chart.yaml Matrix Check
SoT rule: master §4 (Deterministic Architecture), ADR-0008
"""
import argparse
import json
import sys
from pathlib import Path

ROOTS_24 = [
    "01_ai_layer","02_audit_logging","03_core","04_deployment",
    "05_documentation","06_data_pipeline","07_governance_legal","08_identity_score",
    "09_meta_identity","10_interoperability","11_test_simulation","12_tooling",
    "13_ui_layer","14_zero_time_auth","15_infra","16_codex",
    "17_observability","18_data_layer","19_adapters","20_foundation",
    "21_post_quantum_crypto","22_datasets","23_compliance","24_meta_orchestration",
]
SHARDS_16 = [
    "01_identitaet_personen","02_dokumente_nachweise","03_zugang_berechtigungen",
    "04_kommunikation_daten","05_gesundheit_medizin","06_bildung_qualifikationen",
    "07_familie_soziales","08_mobilitaet_fahrzeuge","09_arbeit_karriere",
    "10_finanzen_banking","11_versicherungen_risiken","12_immobilien_grundstuecke",
    "13_unternehmen_gewerbe","14_vertraege_vereinbarungen",
    "15_handel_transaktionen","16_behoerden_verwaltung",
]

def check(repo_root: Path, num_roots: int, num_shards: int, previous_state: dict = None) -> dict:
    total_expected = num_roots * num_shards
    total_found = 0
    missing = []
    by_root = {}

    for root_id in ROOTS_24[:num_roots]:
        root_found = 0
        root_missing = []
        for shard_id in SHARDS_16[:num_shards]:
            chart = repo_root / root_id / "shards" / shard_id / "chart.yaml"
            if chart.exists():
                root_found += 1
                total_found += 1
            else:
                path = f"{root_id}/shards/{shard_id}/chart.yaml"
                root_missing.append(path)
                missing.append(path)
        by_root[root_id] = {
            "expected": num_shards,
            "found": root_found,
            "missing_count": len(root_missing),
        }

    completion_pct = round(total_found / total_expected * 100, 2) if total_expected else 0
    regression = False
    if previous_state and "total_found" in previous_state:
        regression = total_found < previous_state["total_found"]

    if regression:
        status = "FAIL_SHARD"
    elif completion_pct >= 90:
        status = "PASS"
    else:
        status = "WARN"

    return {
        "total_expected": total_expected,
        "total_found": total_found,
        "missing_count": len(missing),
        "completion_percent": completion_pct,
        "status": status,
        "regression_detected": regression,
        "by_root": by_root,
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--roots", type=int, default=24)
    parser.add_argument("--shards", type=int, default=16)
    parser.add_argument("--previous-state", default=None)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    previous_state = None
    if args.previous_state and Path(args.previous_state).exists():
        previous_state = json.loads(Path(args.previous_state).read_text())

    result = check(repo_root, args.roots, args.shards, previous_state)
    print(json.dumps(result, indent=2))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, indent=2))
    pct = result["completion_percent"]
    print(f"Shard completion: {pct}% ({result['total_found']}/{result['total_expected']}) — {result['status']}")
    sys.exit(1 if result["status"] == "FAIL_SHARD" else 0)
