#!/usr/bin/env python3
"""
Erzeugt repo_scan.json als einzige valide OPA-Input-Quelle.
SoT-Regel: master_v1.1.1 §7
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOTS_24 = [
    "01_ai_layer", "02_audit_logging", "03_core", "04_deployment",
    "05_documentation", "06_data_pipeline", "07_governance_legal",
    "08_identity_score", "09_meta_identity", "10_interoperability",
    "11_test_simulation", "12_tooling", "13_ui_layer", "14_zero_time_auth",
    "15_infra", "16_codex", "17_observability", "18_data_layer",
    "19_adapters", "20_foundation", "21_post_quantum_crypto",
    "22_datasets", "23_compliance", "24_meta_orchestration",
]
SHARDS_16 = [
    "01_identitaet_personen", "02_dokumente_nachweise",
    "03_zugang_berechtigungen", "04_kommunikation_daten",
    "05_gesundheit_medizin", "06_bildung_qualifikationen",
    "07_familie_soziales", "08_mobilitaet_fahrzeuge",
    "09_arbeit_karriere", "10_finanzen_banking",
    "11_versicherungen_risiken", "12_immobilien_grundstuecke",
    "13_unternehmen_gewerbe", "14_vertraege_vereinbarungen",
    "15_handel_transaktionen", "16_behoerden_verwaltung",
]
FORBIDDEN_EXTS = {".ipynb", ".parquet", ".sqlite", ".db",
                  ".env", ".pem", ".key", ".p12", ".pfx"}
SKIP_DIRS = {".git", "node_modules", ".venv", ".pytest_cache", "__pycache__"}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    try:
        h.update(path.read_bytes())
    except (PermissionError, OSError):
        return ""
    return h.hexdigest()


def scan(repo_root: Path, commit_sha: str) -> dict:
    repo_root = Path(repo_root).resolve()
    files = []
    forbidden_found = []
    shard_counts = {}

    for root_id in ROOTS_24:
        root_path = repo_root / root_id
        shard_counts[root_id] = 0
        if not root_path.exists():
            continue
        for p in root_path.rglob("*"):
            if p.is_dir():
                continue
            if any(part in SKIP_DIRS for part in p.parts):
                continue
            rel = str(p.relative_to(repo_root))
            ext = p.suffix.lower()
            if ext in FORBIDDEN_EXTS:
                forbidden_found.append(rel)
            if p.name == "chart.yaml" and "/shards/" in rel:
                shard_counts[root_id] += 1
            files.append({
                "path": rel,
                "ext": ext,
                "size_bytes": p.stat().st_size,
                "sha256": sha256_file(p),
                "root": root_id,
            })

    # Also scan files directly in repo_root (not under any known root)
    # for forbidden extension detection when repo_root itself is a tmp dir
    # (no ROOTS_24 subdirs present) — scan all files at root level
    has_any_root = any((repo_root / r).exists() for r in ROOTS_24)
    if not has_any_root:
        for p in repo_root.rglob("*"):
            if p.is_dir():
                continue
            if any(part in SKIP_DIRS for part in p.parts):
                continue
            rel = str(p.relative_to(repo_root))
            ext = p.suffix.lower()
            if ext in FORBIDDEN_EXTS:
                forbidden_found.append(rel)
            files.append({
                "path": rel,
                "ext": ext,
                "size_bytes": p.stat().st_size,
                "sha256": sha256_file(p),
                "root": None,
            })

    incident_plans = {}
    for root_id in ROOTS_24:
        plan_path = repo_root / root_id / "docs" / "incident_response_plan.md"
        incident_plans[root_id] = {
            "exists": plan_path.exists(),
            "path": f"{root_id}/docs/incident_response_plan.md",
        }

    roots = [
        {"id": r, "path": r, "exists": (repo_root / r).exists()}
        for r in ROOTS_24
    ]

    return {
        "scan_ts": datetime.now(timezone.utc).isoformat(),
        "commit_sha": commit_sha,
        "repo": repo_root.name,
        "roots": roots,
        "files": files,
        "forbidden_extensions_found": forbidden_found,
        "shard_counts": shard_counts,
        "chart_yaml_present": {
            f"{r}/shards/{s}": (repo_root / r / "shards" / s / "chart.yaml").exists()
            for r in ROOTS_24
            for s in SHARDS_16
        },
        "incident_response_plans": incident_plans,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    result = scan(args.repo_root, args.commit_sha)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, indent=2))
    print(f"repo_scan.json written to {args.out} ({len(result['files'])} files)")
