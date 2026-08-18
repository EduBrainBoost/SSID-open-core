#!/usr/bin/env python3
"""AGENT 04 — FS-Noise Detection Gate.

Detects filesystem noise artifacts (__pycache__, .pytest_cache, *.pyc,
*.pyo, .mypy_cache) anywhere in the repo tree.  Reports findings as
FAIL with evidence but does NOT auto-clean (developer must run
dev_clean.py manually).

SoT v4.1.0 | ROOT-24-LOCK | Classification: Gate
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

NOISE_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
NOISE_EXTENSIONS = {".pyc", ".pyo"}
SKIP_DIRS = {".git", "node_modules", ".venv", "venv"}

REPO_ROOT = Path(__file__).resolve().parents[4]


def scan_noise(root: Path) -> list[dict]:
    """Scan for filesystem noise artifacts. Returns list of findings."""
    findings: list[dict] = []

    for item in root.rglob("*"):
        # Skip .git and venvs
        if any(part in SKIP_DIRS for part in item.parts):
            continue

        if item.is_dir() and item.name in NOISE_DIRS:
            findings.append({
                "type": "noise_directory",
                "path": str(item.relative_to(root)),
                "artifact": item.name,
            })

        if item.is_file() and item.suffix in NOISE_EXTENSIONS:
            findings.append({
                "type": "noise_file",
                "path": str(item.relative_to(root)),
                "artifact": item.suffix,
            })

    return findings


def generate_evidence(findings: list[dict], root: Path) -> str:
    """Write evidence file and return path."""
    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    evidence_dir = root / "23_compliance" / "evidence" / "ci_runs"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "gate": "fs_noise_detector",
        "timestamp": ts,
        "finding_count": len(findings),
        "status": "FAIL" if findings else "PASS",
        "findings": findings,
    }

    content = json.dumps(report, indent=2, default=str)
    sha = hashlib.sha256(content.encode()).hexdigest()
    report["integrity_sha256"] = sha

    filepath = evidence_dir / f"{ts}_A04_fs_noise.json"
    filepath.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return str(filepath)


def main() -> int:
    root = REPO_ROOT
    if not (root / "16_codex").is_dir():
        print("FS_NOISE_GATE_FAIL: Cannot locate repo root", file=sys.stderr)
        return 1

    findings = scan_noise(root)

    evidence_path = generate_evidence(findings, root)

    if findings:
        print(f"FS_NOISE_GATE_FAIL: {len(findings)} noise artifact(s) detected")
        print(f"  Evidence: {evidence_path}")
        print("  Run: python 12_tooling/scripts/dev_clean.py to remediate")
        for f in findings[:10]:
            print(f"    - [{f['type']}] {f['path']}")
        if len(findings) > 10:
            print(f"    ... and {len(findings) - 10} more")
        return 1

    print("FS_NOISE_GATE_PASS: No noise artifacts detected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
