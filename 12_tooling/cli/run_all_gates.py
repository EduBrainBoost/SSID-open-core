
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
STRUCTURE_GUARD = PROJECT_ROOT / "12_tooling" / "scripts" / "structure_guard.py"
POLICY_PATH = PROJECT_ROOT / "23_compliance" / "policies" / "sot" / "sot_policy.rego"
POLICY_INPUT_PATH = PROJECT_ROOT / "23_compliance" / "inputs" / "repo_minimal.json"
SOT_VALIDATOR = PROJECT_ROOT / "12_tooling" / "cli" / "sot_validator.py"
QA_MASTER = PROJECT_ROOT / "02_audit_logging" / "archives" / "qa_master_suite" / "qa_master_suite.py"
DUPLICATE_GUARD = PROJECT_ROOT / "12_tooling" / "cli" / "duplicate_guard.py"
REPO_SEPARATION_GUARD = PROJECT_ROOT / "12_tooling" / "cli" / "repo_separation_guard.py"
SHARD_GATE = PROJECT_ROOT / "12_tooling" / "cli" / "shard_gate_chart_manifest.py"
CONFORMANCE_GATE = PROJECT_ROOT / "12_tooling" / "cli" / "shard_conformance_gate.py"
SHARDS_REGISTRY_BUILD = PROJECT_ROOT / "12_tooling" / "cli" / "shards_registry_build.py"
LEVEL3_SCAFFOLD = PROJECT_ROOT / "12_tooling" / "cli" / "level3_scaffold.py"
QUARANTINE_VERIFY = PROJECT_ROOT / "12_tooling" / "cli" / "quarantine_verify_chain.py"
E2E_DISPATCHER = PROJECT_ROOT / "24_meta_orchestration" / "dispatcher" / "e2e_dispatcher.py"
PILOT_TASK = PROJECT_ROOT / "24_meta_orchestration" / "queue" / "tasks" / "PILOT_TASK_0001.yaml"
REPORTS_DIR = PROJECT_ROOT / "02_audit_logging" / "reports"
SANDBOX_DIR = PROJECT_ROOT / ".ssid_sandbox"
GITIGNORE_PATH = PROJECT_ROOT / ".gitignore"

EVIDENCE_REQUIRED_ARTIFACTS: list[tuple[str, Path]] = [
    ("sot_registry.json", PROJECT_ROOT / "24_meta_orchestration" / "registry" / "sot_registry.json"),
    ("shards_registry.json", PROJECT_ROOT / "24_meta_orchestration" / "registry" / "shards_registry.json"),
]

E2E_PII_DENY = [
    re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
    re.compile(r"C:[\\\/]Users[\\\/][^\\\/\s\"]+"),
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    re.compile(r'"(first_name|last_name|full_name|surname|vorname|nachname)"'),
]


def _gitignore_has_sandbox_rule() -> bool:
    if not GITIGNORE_PATH.exists():
        return False
    ignore_lines = [line.strip() for line in GITIGNORE_PATH.read_text(encoding="utf-8", errors="replace").splitlines()]
    return ".ssid_sandbox/" in ignore_lines


def _run(cmd: list[str], label: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    print(f"INFO: [GATE] {label}: {' '.join(cmd)}")
    proc = subprocess.run(
        cmd,
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    if proc.returncode != 0:
        print(f"ERROR: {label} failed with exit code {proc.returncode}")
        if proc.stdout:
            print(f"STDOUT:\n{proc.stdout}")
        if proc.stderr:
            print(f"STDERR:\n{proc.stderr}")
    return proc


def run_repo_hygiene_check() -> bool:
    print("INFO: [GATE] Running Sandbox Hygiene Check...")
    if not _gitignore_has_sandbox_rule():
        print("ERROR: .gitignore must contain '.ssid_sandbox/' rule.")
        return False
    if SANDBOX_DIR.exists():
        tracked = _run(["git", "ls-files", "--error-unmatch", ".ssid_sandbox"], "Hygiene (sandbox tracked check)")
        if tracked.returncode == 0:
            print("ERROR: .ssid_sandbox/ is tracked by git (forbidden)")
            return False
        print("INFO: .ssid_sandbox/ exists but is not tracked; allowed for local runs.")
    print("INFO: [GATE] Sandbox Hygiene Check PASSED.")
    return True


def run_git_worktree_check() -> bool:
    print("INFO: [GATE] Running Git Worktree Check...")
    proc = _run(["git", "rev-parse", "--is-inside-work-tree"], "Git Worktree Check")
    if proc.returncode != 0:
        return False
    if (proc.stdout or "").strip().lower() != "true":
        print("ERROR: Not inside a Git worktree.")
        return False
    print("INFO: [GATE] Git Worktree Check PASSED.")
    return True


def run_structure_guard() -> bool:
    """Gate 0: Root structure enforcement (ROOT-24-LOCK)."""
    print("INFO: [GATE] Running Structure Guard...")
    if not STRUCTURE_GUARD.exists():
        print(f"ERROR: Structure guard missing: {STRUCTURE_GUARD}")
        return False
    proc = _run([sys.executable, str(STRUCTURE_GUARD)], "Structure Guard")
    if proc.returncode != 0:
        print(f"ERROR: Structure guard failed (exit={proc.returncode})")
        return False
    print("INFO: [GATE] Structure Guard PASSED.")
    return True


def run_duplicate_guard() -> bool:
    print("INFO: [GATE] Running Duplicate Guard...")
    if not DUPLICATE_GUARD.exists():
        print(f"ERROR: Duplicate guard missing: {DUPLICATE_GUARD}")
        return False
    proc = _run([sys.executable, str(DUPLICATE_GUARD), "--repo-root", str(PROJECT_ROOT)], "Duplicate Guard")
    if proc.returncode != 0:
        return False
    print("INFO: [GATE] Duplicate Guard PASSED.")
    return True


def run_repo_separation_guard() -> bool:
    print("INFO: [GATE] Running Repo Separation Guard...")
    if not REPO_SEPARATION_GUARD.exists():
        print(f"ERROR: Repo separation guard missing: {REPO_SEPARATION_GUARD}")
        return False
    import os
    env = {**os.environ, "GITHUB_BASE_REF": os.environ.get("GITHUB_BASE_REF", "main")}
    proc = _run(
        [sys.executable, str(REPO_SEPARATION_GUARD), "--repo-root", str(PROJECT_ROOT)],
        "Repo Separation Guard",
        env=env,
    )
    if proc.returncode != 0:
        return False
    print("INFO: [GATE] Repo Separation Guard PASSED.")
    return True


def _run_policy_with_opa() -> bool:
    check = _run(["opa", "check", str(POLICY_PATH)], "Policy (OPA check)")
    if check.returncode != 0:
        return False

    test = _run(["opa", "test", str(POLICY_PATH.parent)], "Policy (OPA test)")
    if test.returncode != 0:
        return False

    if not POLICY_INPUT_PATH.exists():
        print(f"ERROR: Policy input file missing: {POLICY_INPUT_PATH}")
        return False

    eval_proc = _run(
        ["opa", "eval", "--format", "json", "-d", str(POLICY_PATH), "-i", str(POLICY_INPUT_PATH), "data.sot_policy.deny"],
        "Policy (OPA eval)",
    )
    if eval_proc.returncode != 0:
        return False

    try:
        payload = json.loads(eval_proc.stdout or "{}")
        results = payload.get("result", [])
        if not results:
            print("ERROR: OPA eval returned no result payload.")
            return False
        deny_entries = results[0]["expressions"][0]["value"]
        if isinstance(deny_entries, list) and deny_entries:
            print(f"ERROR: OPA deny returned violations: {deny_entries}")
            return False
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        print(f"ERROR: Could not parse OPA eval output: {exc}")
        return False

    return True


def run_policy_check() -> bool:
    print("INFO: [GATE] Running Policy Check...")
    if not shutil.which("opa"):
        print("ERROR: OPA executable not found. Deterministic FAIL (no simulation).")
        return False
    if not _run_policy_with_opa():
        return False
    print("INFO: [GATE] Policy Check PASSED.")
    return True


def run_sot_check() -> bool:
    print("INFO: [GATE] Running SoT Validation...")
    if not SOT_VALIDATOR.exists():
        print(f"ERROR: SoT Validator not found at '{SOT_VALIDATOR}'.")
        return False
    proc = _run([sys.executable, str(SOT_VALIDATOR), "--verify-all"], "SoT Validation")
    if proc.returncode != 0:
        return False
    print("INFO: [GATE] SoT Validation PASSED.")
    return True


def run_shard_gate() -> bool:
    """Gate: chart+manifest presence for pilot shards."""
    print("INFO: [GATE] Running Shard Chart+Manifest Gate...")
    if not SHARD_GATE.exists():
        print(f"ERROR: Shard gate missing: {SHARD_GATE}")
        return False
    proc = _run([sys.executable, str(SHARD_GATE), "--root", "03_core", "--pilot"], "Shard Gate")
    if proc.returncode != 0:
        return False
    print("INFO: [GATE] Shard Chart+Manifest Gate PASSED.")
    return True



def run_shard_conformance_gate() -> bool:
    """Gate: conformance validation for pilot shards."""
    print("INFO: [GATE] Running Shard Conformance Gate...")
    if not CONFORMANCE_GATE.exists():
        print(f"ERROR: Conformance gate missing: {CONFORMANCE_GATE}")
        return False
    for shard in ["01_identitaet_personen", "02_dokumente_nachweise"]:
        proc = _run(
            [sys.executable, str(CONFORMANCE_GATE), "--root", "03_core", "--shard", shard],
            f"Conformance Gate ({shard})",
        )
        if proc.returncode != 0:
            return False
    print("INFO: [GATE] Shard Conformance Gate PASSED.")
    return True

def run_evidence_completeness() -> bool:
    """Gate: verify Phase-2 required artifacts exist. FAIL if any missing."""
    print("INFO: [GATE] Running Evidence Completeness Check...")
    missing = []
    for name, path in EVIDENCE_REQUIRED_ARTIFACTS:
        if not path.exists():
            missing.append(name)
            print(f"ERROR: Required artifact missing: {name} ({path.relative_to(PROJECT_ROOT)})")
    if missing:
        print(f"FAIL: Evidence Completeness — {len(missing)} artifact(s) missing: {', '.join(missing)}")
        return False
    # Verify shards_registry.json via --verify
    if SHARDS_REGISTRY_BUILD.exists():
        proc = _run(
            [sys.executable, str(SHARDS_REGISTRY_BUILD), "--verify"],
            "Evidence Completeness (shards_registry --verify)",
        )
        if proc.returncode != 0:
            print("FAIL: shards_registry.json hash verification failed")
            return False
    print("INFO: [GATE] Evidence Completeness Check PASSED.")
    return True

def run_e2e_pipeline_smoke(source: str) -> bool:
    """Gate: build registry + run dispatcher on pilot task."""
    print("INFO: [GATE] Running E2E Pipeline Smoke...")
    if not SHARDS_REGISTRY_BUILD.exists():
        print(f"ERROR: shards_registry_build.py missing: {SHARDS_REGISTRY_BUILD}")
        return False
    proc = _run([sys.executable, str(SHARDS_REGISTRY_BUILD), "--deterministic"], "E2E Registry Build")
    if proc.returncode != 0:
        return False
    if not E2E_DISPATCHER.exists():
        print(f"ERROR: e2e_dispatcher.py missing: {E2E_DISPATCHER}")
        return False
    if not PILOT_TASK.exists():
        print(f"ERROR: Pilot task missing: {PILOT_TASK}")
        return False
    proc = _run(
        [sys.executable, str(E2E_DISPATCHER), "run-task",
         "--task", str(PILOT_TASK), "--source", source, "--deterministic"],
        "E2E Dispatcher run-task",
    )
    if proc.returncode != 0:
        return False
    print("INFO: [GATE] E2E Pipeline Smoke PASSED.")
    return True


def _find_latest_e2e_run() -> Path | None:
    runs = sorted(REPORTS_DIR.glob("E2E_RUN_*.json"))
    return runs[-1] if runs else None


def run_e2e_report_schema_check() -> bool:
    """Gate: validate latest E2E report files have required keys."""
    print("INFO: [GATE] Running E2E Report Schema Check...")
    latest = _find_latest_e2e_run()
    if latest is None:
        print("ERROR: No E2E_RUN_*.json found in reports")
        return False
    run_id = latest.stem.replace("E2E_RUN_", "")

    # Check E2E_RUN
    try:
        data = json.loads(latest.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"ERROR: Cannot parse {latest.name}: {exc}")
        return False
    required = ["schema_version", "run_id", "source", "git_sha", "task", "resolved", "hashes", "timing", "status", "violations"]
    missing = [k for k in required if k not in data]
    if missing:
        print(f"FAIL: E2E_RUN missing keys: {missing}")
        return False

    # Check RUN_LOG
    log_path = REPORTS_DIR / f"RUN_LOG_{run_id}.jsonl"
    if not log_path.exists():
        print(f"FAIL: RUN_LOG_{run_id}.jsonl missing")
        return False
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    events = {json.loads(l).get("event") for l in lines}
    required_events = {"TASK_RECEIVED", "ROUTE_RESOLVED", "SHARD_STARTED", "SHARD_FINISHED", "REPORT_WRITTEN"}
    if not required_events.issubset(events):
        print(f"FAIL: RUN_LOG missing events: {required_events - events}")
        return False

    # Check HASHES
    hashes_path = REPORTS_DIR / f"E2E_ARTIFACT_HASHES_{run_id}.json"
    if not hashes_path.exists():
        print(f"FAIL: E2E_ARTIFACT_HASHES_{run_id}.json missing")
        return False

    print("INFO: [GATE] E2E Report Schema Check PASSED.")
    return True


def run_e2e_no_pii_check() -> bool:
    """Gate: scan latest E2E reports for PII patterns."""
    print("INFO: [GATE] Running E2E No-PII Check...")
    latest = _find_latest_e2e_run()
    if latest is None:
        print("ERROR: No E2E_RUN found")
        return False
    run_id = latest.stem.replace("E2E_RUN_", "")
    report_files = [
        REPORTS_DIR / f"E2E_RUN_{run_id}.json",
        REPORTS_DIR / f"RUN_LOG_{run_id}.jsonl",
        REPORTS_DIR / f"E2E_ARTIFACT_HASHES_{run_id}.json",
    ]
    for rp in report_files:
        if not rp.exists():
            continue
        content = rp.read_text(encoding="utf-8")
        for pat in E2E_PII_DENY:
            matches = pat.findall(content)
            if matches:
                print(f"FAIL: PII pattern {pat.pattern} found in {rp.name}: {matches[:3]}")
                return False
    print("INFO: [GATE] E2E No-PII Check PASSED.")
    return True


def run_e2e_determinism_check() -> bool:
    """Gate: recompute expected run_id and compare with report (single-run stable)."""
    print("INFO: [GATE] Running E2E Determinism Check...")
    latest = _find_latest_e2e_run()
    if latest is None:
        print("ERROR: No E2E_RUN found")
        return False
    data = json.loads(latest.read_text(encoding="utf-8"))
    task = data.get("task", {})
    payload = (
        data.get("git_sha", "")
        + task.get("task_id", "")
        + task.get("root_id", "")
        + task.get("shard_id", "")
        + task.get("action", "")
        + task.get("inputs_hash", "")
    )
    expected = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    actual = data.get("run_id", "")
    if expected != actual:
        print(f"FAIL: run_id mismatch: expected={expected} actual={actual}")
        return False
    print("INFO: [GATE] E2E Determinism Check PASSED.")
    return True


def run_l3_scaffold_check() -> bool:
    """Gate: verify all 24 roots have L3 scaffold files."""
    print("INFO: [GATE] Running L3 Scaffold Presence Check...")
    if not LEVEL3_SCAFFOLD.exists():
        print(f"ERROR: L3 scaffold script missing: {LEVEL3_SCAFFOLD}")
        return False
    proc = _run(
        [sys.executable, str(LEVEL3_SCAFFOLD), "--all", "--check"],
        "L3 Scaffold Presence",
    )
    if proc.returncode != 0:
        print("FAIL: L3 scaffold files missing in one or more roots")
        return False
    print("INFO: [GATE] L3 Scaffold Presence Check PASSED.")
    return True


def run_quarantine_chain_verify() -> bool:
    """Gate: verify quarantine chain append-only integrity."""
    print("INFO: [GATE] Running Quarantine Chain Verify...")
    if not QUARANTINE_VERIFY.exists():
        print(f"ERROR: Quarantine verify script missing: {QUARANTINE_VERIFY}")
        return False
    proc = _run(
        [sys.executable, str(QUARANTINE_VERIFY)],
        "Quarantine Chain Verify",
    )
    if proc.returncode != 0:
        print("FAIL: Quarantine chain integrity verification failed")
        return False
    print("INFO: [GATE] Quarantine Chain Verify PASSED.")
    return True


def run_qa_check() -> bool:
    print("INFO: [GATE] Running QA Check...")
    if not QA_MASTER.exists():
        print(f"ERROR: QA master suite missing: {QA_MASTER}")
        return False
    proc = _run([sys.executable, str(QA_MASTER), "--mode", "minimal"], "QA Master Suite")
    if proc.returncode != 0:
        return False
    print("INFO: [GATE] QA Check PASSED.")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local CI-equivalent gates (real enforcement only).")
    parser.add_argument("--policy-only", action="store_true", help="Run only hygiene + duplicate + policy gate.")
    parser.add_argument("--qa-only", action="store_true", help="Run only hygiene + duplicate + QA gate.")
    parser.add_argument("--e2e-only", action="store_true", help="Run only E2E pipeline gates (skip policy/sot/shard).")
    parser.add_argument("--source", choices=["local-run", "ci-run"], default="local-run")
    args = parser.parse_args()

    exclusive = sum([args.policy_only, args.qa_only, args.e2e_only])
    if exclusive > 1:
        print("ERROR: --policy-only, --qa-only, --e2e-only are mutually exclusive.")
        return 2

    if not run_git_worktree_check():
        return 1

    # E2E-only skips repo-structure pre-gates (structure guard, hygiene, etc.)
    if args.e2e_only:
        print("--- Running in E2E-Only Mode ---")
        if not run_e2e_pipeline_smoke(args.source):
            print("\nERROR: E2E Pipeline Smoke failed.")
            return 1
        if not run_e2e_report_schema_check():
            print("\nERROR: E2E Report Schema Check failed.")
            return 1
        if not run_e2e_no_pii_check():
            print("\nERROR: E2E No-PII Check failed.")
            return 1
        if not run_e2e_determinism_check():
            print("\nERROR: E2E Determinism Check failed.")
            return 1
        print("\n--- All E2E Gates PASSED ---")
        return 0

    # Pre-gates for policy-only, qa-only, and full chain
    if not run_structure_guard():
        return 1
    if not run_repo_hygiene_check():
        return 1
    if not run_repo_separation_guard():
        return 1
    if not run_duplicate_guard():
        return 1

    if args.policy_only:
        print("--- Running in Policy-Only Mode ---")
        return 0 if run_policy_check() else 1

    if args.qa_only:
        print("--- Running in QA-Only Mode ---")
        return 0 if run_qa_check() else 1

    print("--- Running Full Gate Chain: Policy -> SoT -> Shard -> Conformance -> Evidence -> L3 Scaffold -> Quarantine -> E2E -> QA ---")
    if not run_policy_check():
        print("\nERROR: Gate chain failed at Policy Check.")
        return 1
    if not run_sot_check():
        print("\nERROR: Gate chain failed at SoT Validation.")
        return 1
    if not run_shard_gate():
        print("\nERROR: Gate chain failed at Shard Gate.")
        return 1
    if not run_shard_conformance_gate():
        print("\nERROR: Gate chain failed at Shard Conformance Gate.")
        return 1
    if not run_evidence_completeness():
        print("\nERROR: Gate chain failed at Evidence Completeness.")
        return 1
    if not run_l3_scaffold_check():
        print("\nERROR: Gate chain failed at L3 Scaffold Presence.")
        return 1
    if not run_quarantine_chain_verify():
        print("\nERROR: Gate chain failed at Quarantine Chain Verify.")
    if not run_e2e_pipeline_smoke(args.source):
        print("\nERROR: Gate chain failed at E2E Pipeline Smoke.")
        return 1
    if not run_e2e_report_schema_check():
        print("\nERROR: Gate chain failed at E2E Report Schema Check.")
        return 1
    if not run_e2e_no_pii_check():
        print("\nERROR: Gate chain failed at E2E No-PII Check.")
        return 1
    if not run_e2e_determinism_check():
        print("\nERROR: Gate chain failed at E2E Determinism Check.")
        return 1
    if not run_qa_check():
        print("\nERROR: Gate chain failed at QA Check.")
        return 1

    print("\n--- All Gates PASSED Successfully ---")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
