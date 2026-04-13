#!/usr/bin/env python3
"""Artifact Drift Gate — detect divergence between SoT and deploy-path artifacts.

Compares SHA256 hashes of contract artifacts in:
  - 24_meta_orchestration/contracts/  (canonical SoT)
  - 12_tooling/testnet_mvp/01_hash_only_proof_registry/contracts/  (deploy path)

Exit 0 = no drift (PASS).
Exit 1 = drift detected (FAIL).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOT_DIR = PROJECT_ROOT / "24_meta_orchestration" / "contracts"
DEPLOY_DIR = PROJECT_ROOT / "12_tooling" / "testnet_mvp" / "01_hash_only_proof_registry" / "contracts"

ARTIFACT_FILES = [
    "proof_registry_abi.json",
    "proof_registry_bytecode.json",
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_drift() -> list[str]:
    """Return list of drift findings (empty = no drift)."""
    findings: list[str] = []

    for fname in ARTIFACT_FILES:
        sot_path = SOT_DIR / fname
        deploy_path = DEPLOY_DIR / fname

        if not sot_path.exists():
            findings.append(f"SoT artifact missing: {fname}")
            continue
        if not deploy_path.exists():
            findings.append(f"Deploy artifact missing: {fname}")
            continue

        sot_hash = _sha256(sot_path)
        deploy_hash = _sha256(deploy_path)

        if sot_hash != deploy_hash:
            findings.append(f"Drift in {fname}: SoT={sot_hash[:16]}... deploy={deploy_hash[:16]}...")

    return findings


def main() -> int:
    print("INFO: [GATE] Running Artifact Drift Gate...")
    findings = check_drift()

    if findings:
        for f in findings:
            print(f"ERROR: {f}")
        print(f"FAIL: Artifact Drift Gate — {len(findings)} drift(s) detected")
        return 1

    print("INFO: [GATE] Artifact Drift Gate PASSED.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
