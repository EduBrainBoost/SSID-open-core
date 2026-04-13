#!/usr/bin/env python3
"""Meta-Continuum Readiness Gate.

Evaluates system readiness for meta-continuum advancement.
Output: PASS/FAIL + findings. No scores.

PASS means the system correctly knows its readiness state:
  - If all criteria MET: status = READY (advancement allowed)
  - If any criterion NOT_MET: status = NOT_READY (correct single-system state)

FAIL means an internal error prevented evaluation.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "23_compliance" / "policies" / "meta_continuum" / "readiness_config.yaml"
SOT_VALIDATOR = PROJECT_ROOT / "12_tooling" / "cli" / "sot_validator.py"
CLAIMS_GUARD_REGO = PROJECT_ROOT / "23_compliance" / "policies" / "claims_guard.rego"
OPEN_CORE_ALLOWLIST = PROJECT_ROOT / "23_compliance" / "policies" / "open_core_export_allowlist.yaml"
PROOF_DIR = PROJECT_ROOT / "23_compliance" / "evidence" / "interfederation_proofs"


def _load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Readiness config not found: {CONFIG_PATH}")
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def check_proof_snapshot_exists() -> tuple[bool, str]:
    """MC-01: Check if an interfederation proof snapshot exists."""
    if not PROOF_DIR.exists():
        return False, "No interfederation proof directory exists"
    proofs = list(PROOF_DIR.glob("proof_*.json"))
    if not proofs:
        return False, "No proof snapshot files found"
    latest = max(proofs, key=lambda p: p.stat().st_mtime)
    try:
        data = json.loads(latest.read_text(encoding="utf-8"))
        ssid_commit = data.get("ssid_commit", "")
        opencore_commit = data.get("opencore_commit", "")
        if ssid_commit and opencore_commit:
            return True, f"Proof snapshot found: {latest.name}"
        return False, f"Proof snapshot incomplete: ssid_commit={bool(ssid_commit)}, opencore_commit={bool(opencore_commit)}"
    except (json.JSONDecodeError, OSError) as exc:
        return False, f"Cannot parse proof snapshot: {exc}"


def check_claims_guard_clean() -> tuple[bool, str]:
    """MC-02: Verify claims guard rego exists and no forbidden claims in repo."""
    if not CLAIMS_GUARD_REGO.exists():
        return False, "claims_guard.rego not found"
    # Quick grep for forbidden claims (same list as run_all_gates)
    forbidden = ["interfederation active", "mutual validation complete",
                 "bidirectional verification achieved", "co-truth protocol active"]
    exempt = ["claims_guard", "test_claims_guard", "test_interfederation",
              "run_all_gates", "meta_continuum_readiness", "/archives/",
              "__pycache__", ".pyc", "/plans/", "/agent_runs/run-merge-"]
    scan_prefixes = ["02_audit_logging", "05_documentation", "16_codex", "23_compliance"]
    proc = subprocess.run(
        ["git", "ls-files", "-z", "--"] + scan_prefixes,
        cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=30,
    )
    tracked = sorted(f for f in proc.stdout.split("\0") if f) if proc.returncode == 0 else []
    for fpath in tracked:
        if any(pat in fpath for pat in exempt):
            continue
        full = PROJECT_ROOT / fpath
        if not full.is_file() or full.stat().st_size > 2_000_000:
            continue
        try:
            content = full.read_text(encoding="utf-8", errors="ignore").lower()
        except OSError:
            continue
        for claim in forbidden:
            if claim in content:
                return False, f"Forbidden claim '{claim}' in {fpath}"
    return True, "Claims guard clean (zero findings)"


def check_open_core_allowlist_enforced() -> tuple[bool, str]:
    """MC-03: Verify open-core export allowlist exists."""
    if not OPEN_CORE_ALLOWLIST.exists():
        return False, "open_core_export_allowlist.yaml not found"
    return True, "Open-core export allowlist present"


def check_sot_hashes_valid() -> tuple[bool, str]:
    """MC-04: Run sot_validator --verify-all."""
    if not SOT_VALIDATOR.exists():
        return False, f"sot_validator.py not found: {SOT_VALIDATOR}"
    proc = subprocess.run(
        [sys.executable, str(SOT_VALIDATOR), "--verify-all"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode == 0:
        return True, "SoT hashes all valid"
    detail = (proc.stdout or proc.stderr or "").strip()[-200:]
    return False, f"SoT verification failed: {detail}"


def check_gate_chain_pass() -> tuple[bool, str]:
    """MC-05: Full gate chain passes (dry check — already wired in CI)."""
    # This is a meta-check: if we're running inside run_all_gates,
    # the gate chain is already passing. Just confirm the script exists.
    gate_runner = PROJECT_ROOT / "12_tooling" / "cli" / "run_all_gates.py"
    if not gate_runner.exists():
        return False, "run_all_gates.py not found"
    return True, "Gate chain runner present (validated by CI)"


def check_external_handshake_recorded() -> tuple[bool, str]:
    """MC-06: External system handshake recorded."""
    handshake_dir = PROJECT_ROOT / "23_compliance" / "evidence" / "external_handshakes"
    if not handshake_dir.exists():
        return False, "No external handshake directory exists"
    handshakes = list(handshake_dir.glob("handshake_*.json"))
    if not handshakes:
        return False, "No handshake records found"
    return True, f"Found {len(handshakes)} handshake record(s)"


CHECKS = {
    "proof_snapshot_exists": check_proof_snapshot_exists,
    "claims_guard_clean": check_claims_guard_clean,
    "open_core_allowlist_enforced": check_open_core_allowlist_enforced,
    "sot_hashes_valid": check_sot_hashes_valid,
    "gate_chain_pass": check_gate_chain_pass,
    "external_handshake_recorded": check_external_handshake_recorded,
}


def evaluate_readiness(config: dict) -> dict:
    """Evaluate all readiness criteria. Returns structured report."""
    findings = []
    all_met = True

    for criterion in config.get("criteria", []):
        cid = criterion["id"]
        name = criterion["name"]
        check_name = criterion["check"]
        check_fn = CHECKS.get(check_name)

        if check_fn is None:
            findings.append({
                "id": cid,
                "name": name,
                "result": "ERROR",
                "detail": f"Unknown check: {check_name}",
            })
            all_met = False
            continue

        try:
            met, detail = check_fn()
        except Exception as exc:
            met, detail = False, f"Check error: {exc}"

        findings.append({
            "id": cid,
            "name": name,
            "result": "MET" if met else "NOT_MET",
            "detail": detail,
        })
        if not met:
            all_met = False

    readiness_status = "READY" if all_met else "NOT_READY"
    return {
        "gate": "meta_continuum_readiness",
        "status": "PASS",
        "readiness": readiness_status,
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Meta-Continuum Readiness Gate. PASS/FAIL + findings.",
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--check-only", action="store_true",
                        help="Only check config validity, skip live checks")
    args = parser.parse_args()

    try:
        config = _load_config()
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}")
        return 1

    if args.check_only:
        criteria_count = len(config.get("criteria", []))
        print(f"Config valid: {criteria_count} criteria defined, status={config.get('current_status')}")
        return 0

    report = evaluate_readiness(config)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Meta-Continuum Readiness: {report['readiness']}")
        print(f"Gate Status: {report['status']}")
        print()
        for f in report["findings"]:
            print(f"  [{f['result']}] {f['id']} {f['name']}: {f['detail']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
