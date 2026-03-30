#!/usr/bin/env python3
"""
sot_convergence_scanner.py — Scan all 5 SoT manifestations and report
convergence status per rule.

Manifestation layers:
  1. Python  — 03_core/validators/sot/sot_validator_core.py  (SOT_AGENT_xxx)
  2. Rego    — 23_compliance/policies/rego/*.rego
  3. YAML    — 16_codex/rules/chunks/*.yaml
  4. CLI     — 12_tooling/cli/sot_enforcement_gate.py
  5. Test    — 11_test_simulation/tests_compliance/test_sot_validator.py

For each rule-ID found in any manifestation, the scanner checks presence in
all 5 layers and flags: CONVERGED, DRIFT, MISSING, DUPLICATE.

Usage:
    python sot_convergence_scanner.py --report <output_path.json>
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# Rule-ID pattern: SOT_AGENT_NNN or SOT_NNN or RULE-NNN
RULE_ID_RE = re.compile(r"\b(SOT_AGENT_\d{3}|SOT_\d{3}|RULE-\d{3,4})\b")

MANIFESTATION_DEFS: list[dict] = [
    {
        "name": "python",
        "label": "Python Validator",
        "glob": "03_core/validators/sot/**/*.py",
        "paths": ["03_core/validators/sot/"],
    },
    {
        "name": "rego",
        "label": "Rego Policies",
        "glob": "23_compliance/policies/rego/**/*.rego",
        "paths": ["23_compliance/policies/rego/", "23_compliance/policies/"],
    },
    {
        "name": "yaml",
        "label": "YAML Rule Chunks",
        "glob": "16_codex/rules/chunks/**/*.yaml",
        "paths": ["16_codex/rules/chunks/"],
    },
    {
        "name": "cli",
        "label": "CLI Enforcement Gate",
        "glob": "12_tooling/cli/sot_enforcement_gate.py",
        "paths": ["12_tooling/cli/"],
    },
    {
        "name": "test",
        "label": "Test Suite",
        "glob": "11_test_simulation/tests_compliance/test_sot_validator.py",
        "paths": ["11_test_simulation/tests_compliance/"],
    },
]


def find_repo_root(start: Path | None = None) -> Path:
    """Walk up from start to find the repo root (contains 03_core)."""
    cur = start or Path(__file__).resolve().parent
    for _ in range(10):
        if (cur / "03_core").is_dir():
            return cur
        cur = cur.parent
    # fallback: CWD
    if (Path.cwd() / "03_core").is_dir():
        return Path.cwd()
    sys.exit("ERROR: Cannot locate repo root (expected 03_core/).")


def collect_rule_ids_from_file(filepath: Path) -> list[str]:
    """Extract all rule IDs from a single file."""
    if not filepath.exists():
        return []
    try:
        text = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []
    return RULE_ID_RE.findall(text)


def scan_manifestation(repo: Path, mdef: dict) -> dict[str, int]:
    """Scan a manifestation layer and return {rule_id: count}."""
    counts: dict[str, int] = defaultdict(int)
    for base_path in mdef["paths"]:
        full = repo / base_path
        if not full.exists():
            continue
        if full.is_file():
            for rid in collect_rule_ids_from_file(full):
                counts[rid] += 1
        else:
            for root, _dirs, files in os.walk(full):
                for fn in files:
                    fp = Path(root) / fn
                    if fp.suffix in (".py", ".rego", ".yaml", ".yml"):
                        for rid in collect_rule_ids_from_file(fp):
                            counts[rid] += 1
    return dict(counts)


def determine_status(
    rule_id: str,
    presence: dict[str, dict[str, int]],
    layers: list[str],
) -> str:
    """Determine convergence status for a rule."""
    present_in = [l for l in layers if rule_id in presence[l]]
    if len(present_in) == len(layers):
        # Check duplicates
        for l in layers:
            if presence[l].get(rule_id, 0) > 1:
                return "DUPLICATE"
        return "CONVERGED"
    if len(present_in) == 0:
        return "MISSING"
    return "DRIFT"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SoT Convergence Scanner")
    parser.add_argument("--report", required=True, help="Output JSON report path")
    parser.add_argument("--repo", default=None, help="Repo root override")
    args = parser.parse_args(argv)

    repo = find_repo_root(Path(args.repo) if args.repo else None)
    layer_names = [m["name"] for m in MANIFESTATION_DEFS]

    # Scan each manifestation
    presence: dict[str, dict[str, int]] = {}
    scan_meta: list[dict] = []
    all_rule_ids: set[str] = set()

    for mdef in MANIFESTATION_DEFS:
        counts = scan_manifestation(repo, mdef)
        presence[mdef["name"]] = counts
        all_rule_ids.update(counts.keys())
        scan_meta.append({
            "name": mdef["name"],
            "label": mdef["label"],
            "rules_found": len(counts),
        })

    # Evaluate convergence per rule
    rules_report: list[dict] = []
    status_summary: dict[str, int] = defaultdict(int)

    for rid in sorted(all_rule_ids):
        status = determine_status(rid, presence, layer_names)
        status_summary[status] += 1
        present_in = [l for l in layer_names if rid in presence[l]]
        missing_from = [l for l in layer_names if rid not in presence[l]]
        rules_report.append({
            "rule_id": rid,
            "convergence_status": status,
            "present_in": present_in,
            "missing_from": missing_from,
        })

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(repo),
        "manifestation_layers": scan_meta,
        "total_unique_rules": len(all_rule_ids),
        "status_summary": dict(status_summary),
        "rules": rules_report,
    }

    out = Path(args.report)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)

    print(f"Convergence scan complete: {len(all_rule_ids)} rules across {len(layer_names)} layers.")
    print(f"  CONVERGED:  {status_summary.get('CONVERGED', 0)}")
    print(f"  DRIFT:      {status_summary.get('DRIFT', 0)}")
    print(f"  MISSING:    {status_summary.get('MISSING', 0)}")
    print(f"  DUPLICATE:  {status_summary.get('DUPLICATE', 0)}")
    print(f"Report: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
