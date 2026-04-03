
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os as _os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# Windows cp1252 safety: reconfigure stdout/stderr to UTF-8 with replacement
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def parse_guard_mode() -> str:
    """Read SSID_GUARD_MODE from env. Returns 'off', 'soft', or 'hard'. Default: 'soft'.

    Accepts canonical values (off/soft/hard) and v2 aliases (disabled/advisory/strict).
    """
    raw = _os.environ.get("SSID_GUARD_MODE", "soft").strip().lower()
    # v2 alias mapping: strict->hard, advisory->soft, disabled->off
    alias_map = {"strict": "hard", "advisory": "soft", "disabled": "off"}
    normalized = alias_map.get(raw, raw)
    if normalized in ("off", "soft", "hard"):
        return normalized
    print(f"WARN: SSID_GUARD_MODE={raw!r} invalid, falling back to 'soft'", file=sys.stderr)
    return "soft"


def guard_exit_code(mode: str) -> int:
    """Exit code for guard failures: hard=2, soft/off=0."""
    return 2 if mode == "hard" else 0


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
META_READINESS = PROJECT_ROOT / "12_tooling" / "cli" / "meta_continuum_readiness.py"
ARTIFACT_DRIFT_GATE = PROJECT_ROOT / "12_tooling" / "cli" / "artifact_drift_gate.py"
GATE_CONVERGENCE = PROJECT_ROOT / "12_tooling" / "cli" / "gate_convergence_check.py"
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


def _tracked_files_in_dirs(prefixes: list[str]) -> list[str]:
    """Return sorted list of git-tracked files under the given directory prefixes."""
    proc = subprocess.run(
        ["git", "ls-files", "-z", "--"] + prefixes,
        cwd=str(PROJECT_ROOT),
        capture_output=True, text=True, timeout=30,
    )
    if proc.returncode != 0:
        return []
    files = [f for f in proc.stdout.split("\0") if f]
    files.sort()
    return files


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
    proc = _run(
        [sys.executable, str(REPO_SEPARATION_GUARD), "--repo-root", str(PROJECT_ROOT)],
        "Repo Separation Guard",
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


def run_gate_convergence_check() -> bool:
    """Gate: cross-gate convergence validation."""
    print("INFO: [GATE] Running Gate Convergence Check...")
    if not GATE_CONVERGENCE.exists():
        print(f"ERROR: Gate convergence check missing: {GATE_CONVERGENCE}")
        return False
    proc = _run(
        [sys.executable, str(GATE_CONVERGENCE), "--repo-root", str(PROJECT_ROOT)],
        "Gate Convergence Check",
    )
    if proc.returncode == 2:
        print("WARN: Gate Convergence Check returned WARN — proceeding.")
        print(f"INFO: [GATE] Gate Convergence evidence: {GATE_CONVERGENCE}")
        print("INFO: [GATE] Gate Convergence Check PASSED (with warnings).")
        return True
    if proc.returncode != 0:
        print(f"INFO: [GATE] Gate Convergence evidence: {GATE_CONVERGENCE}")
        return False
    print(f"INFO: [GATE] Gate Convergence evidence: {GATE_CONVERGENCE}")
    print("INFO: [GATE] Gate Convergence Check PASSED.")
    return True


def run_artifact_drift_gate() -> bool:
    """Gate: detect drift between SoT and deploy-path contract artifacts."""
    print("INFO: [GATE] Running Artifact Drift Gate...")
    if not ARTIFACT_DRIFT_GATE.exists():
        print(f"ERROR: Artifact drift gate missing: {ARTIFACT_DRIFT_GATE}")
        return False
    proc = _run([sys.executable, str(ARTIFACT_DRIFT_GATE)], "Artifact Drift Gate")
    if proc.returncode != 0:
        return False
    print("INFO: [GATE] Artifact Drift Gate PASSED.")
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


CLAIMS_GUARD_REGO = PROJECT_ROOT / "23_compliance" / "policies" / "claims_guard.rego"
INTERFEDERATION_FORBIDDEN_CLAIMS = [
    "interfederation active",
    "interfederation certified",
    "execution ready",
    "perfect certified",
    "mutual validation complete",
    "bidirectional verification achieved",
    "co-truth protocol active",
    "proof nexus certified",
    "cross-system verified",
    "meta-continuum ready",
]
INTERFEDERATION_SCAN_DIRS = [
    PROJECT_ROOT / "02_audit_logging",
    PROJECT_ROOT / "03_core",
    PROJECT_ROOT / "05_documentation",
    PROJECT_ROOT / "12_tooling",
    PROJECT_ROOT / "16_codex",
    PROJECT_ROOT / "23_compliance",
]
CLAIMS_EXEMPT_PATTERNS = [
    "claims_guard",
    "test_claims_guard",
    "test_interfederation",
    "run_all_gates",
    "meta_continuum_readiness",
    "/archives/",
    "/.git/",
    "__pycache__",
    ".pyc",
    "/plans/",
    "/agent_runs/run-merge-",
]


def run_interfederation_claims_guard() -> bool:
    """Scan repo for forbidden interfederation/certification claims without proof."""
    print("INFO: [GATE] Running Interfederation Claims Guard...")
    # OPA check on claims_guard.rego (if present)
    if CLAIMS_GUARD_REGO.exists() and shutil.which("opa"):
        proc = _run(["opa", "check", str(CLAIMS_GUARD_REGO)], "Claims Guard (OPA check)")
        if proc.returncode != 0:
            return False
    # Repo-wide scan (tracked files only — avoids timeouts on large evidence dirs)
    findings: list[str] = []
    tracked = _tracked_files_in_dirs(
        [str(d.relative_to(PROJECT_ROOT)) for d in INTERFEDERATION_SCAN_DIRS],
    )
    for fpath in tracked:
        if any(pat in fpath for pat in CLAIMS_EXEMPT_PATTERNS):
            continue
        full = PROJECT_ROOT / fpath
        if not full.is_file() or full.stat().st_size > 2_000_000:
            continue
        try:
            content = full.read_text(encoding="utf-8", errors="ignore").lower()
        except OSError:
            continue
        for claim in INTERFEDERATION_FORBIDDEN_CLAIMS:
            if claim in content:
                findings.append(f"Forbidden claim '{claim}' in {fpath}")
    if findings:
        for finding in findings:
            print(f"ERROR: {finding}")
        return False
    print("INFO: [GATE] Interfederation Claims Guard PASSED.")
    return True


def run_interfederation_spec_only() -> bool:
    """Gate: verify no tracked interfederation paths outside allowlist."""
    print("INFO: [GATE] Running Interfederation SPEC-ONLY Path Check...")
    import importlib.util
    spec = importlib.util.spec_from_file_location("sot_validator_cli", str(SOT_VALIDATOR))
    if spec is None or spec.loader is None:
        print(f"ERROR: Cannot load {SOT_VALIDATOR}")
        return False
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    forbidden = mod.check_interfederation_paths(PROJECT_ROOT)
    if forbidden:
        print(f"FAIL: {len(forbidden)} forbidden interfederation path(s):")
        for p in forbidden:
            print(f"  {p}")
        return False
    print("INFO: [GATE] Interfederation SPEC-ONLY Path Check PASSED.")
    return True


def run_meta_continuum_readiness() -> bool:
    """Gate: meta-continuum readiness evaluation (PASS = correctly reports state)."""
    print("INFO: [GATE] Running Meta-Continuum Readiness Gate...")
    if not META_READINESS.exists():
        print(f"ERROR: Meta-continuum readiness tool missing: {META_READINESS}")
        return False
    proc = _run(
        [sys.executable, str(META_READINESS), "--json"],
        "Meta-Continuum Readiness",
    )
    if proc.returncode != 0:
        return False
    try:
        data = json.loads(proc.stdout or "{}")
        status = data.get("status")
        readiness = data.get("readiness")
        if status != "PASS":
            print(f"ERROR: Readiness gate returned status={status}")
            return False
        print(f"INFO: [GATE] Meta-Continuum Readiness: {readiness}")
    except (json.JSONDecodeError, KeyError) as exc:
        print(f"ERROR: Cannot parse readiness output: {exc}")
        return False
    print("INFO: [GATE] Meta-Continuum Readiness Gate PASSED.")
    return True


def _execute_gate_chain(args: argparse.Namespace, guard_mode: str) -> tuple[int, str | None, int]:
    """Execute the gate chain.

    Returns (exit_code, failed_gate_name_or_None, gates_run_count).
    Stop-on-first-fail: returns immediately on first gate failure.
    """
    gates_run = 0

    if not run_git_worktree_check():
        return (guard_exit_code(guard_mode), "git_worktree_check", 0)

    # E2E-only skips repo-structure pre-gates
    if args.e2e_only:
        print("--- Running in E2E-Only Mode ---")
        gates = [
            ("e2e_pipeline_smoke", lambda: run_e2e_pipeline_smoke(args.source)),
            ("e2e_report_schema", run_e2e_report_schema_check),
            ("e2e_no_pii", run_e2e_no_pii_check),
            ("e2e_determinism", run_e2e_determinism_check),
        ]
        for name, fn in gates:
            gates_run += 1
            if not fn():
                print(f"\nERROR: Gate chain failed at {name}.")
                return (guard_exit_code(guard_mode), name, gates_run)
        print("\n--- All E2E Gates PASSED ---")
        return (0, None, gates_run)

    # Pre-gates for all non-e2e modes
    pre_gates = [
        ("structure_guard", run_structure_guard),
        ("repo_hygiene", run_repo_hygiene_check),
        ("repo_separation", run_repo_separation_guard),
        ("duplicate_guard", run_duplicate_guard),
    ]
    for name, fn in pre_gates:
        gates_run += 1
        if not fn():
            return (guard_exit_code(guard_mode), name, gates_run)

    if args.policy_only:
        print("--- Running in Policy-Only Mode ---")
        gates_run += 1
        result = run_policy_check()
        return (0 if result else 1, None if result else "policy", gates_run)

    if args.qa_only:
        print("--- Running in QA-Only Mode ---")
        gates_run += 1
        result = run_qa_check()
        return (0 if result else 1, None if result else "qa", gates_run)

    # Full gate chain
    full_gates = [
        ("interfederation_claims", run_interfederation_claims_guard),
        ("interfederation_spec_only", run_interfederation_spec_only),
        ("meta_continuum_readiness", run_meta_continuum_readiness),
    ]
    for name, fn in full_gates:
        gates_run += 1
        if not fn():
            print(f"\nERROR: Gate chain failed at {name}.")
            return (guard_exit_code(guard_mode), name, gates_run)

    print("--- Running Full Gate Chain: InterfedGuard -> SpecOnly -> Readiness -> Policy -> Convergence -> SoT -> Shard -> Conformance -> Evidence -> L3 Scaffold -> Quarantine -> E2E -> QA ---")
    main_gates = [
        ("policy", run_policy_check),
        ("gate_convergence", run_gate_convergence_check),
        ("sot", run_sot_check),
        ("shard_gate", run_shard_gate),
        ("shard_conformance", run_shard_conformance_gate),
        ("evidence_completeness", run_evidence_completeness),
        ("l3_scaffold", run_l3_scaffold_check),
        ("quarantine_chain", run_quarantine_chain_verify),
        ("artifact_drift_gate", run_artifact_drift_gate),
        ("e2e_pipeline_smoke", lambda: run_e2e_pipeline_smoke(args.source)),
        ("e2e_report_schema", run_e2e_report_schema_check),
        ("e2e_no_pii", run_e2e_no_pii_check),
        ("e2e_determinism", run_e2e_determinism_check),
        ("qa", run_qa_check),
    ]
    for name, fn in main_gates:
        gates_run += 1
        if not fn():
            print(f"\nERROR: Gate chain failed at {name}.")
            return (guard_exit_code(guard_mode), name, gates_run)

    print("\n--- All Gates PASSED Successfully ---")
    return (0, None, gates_run)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local CI-equivalent gates (real enforcement only).")
    parser.add_argument("--policy-only", action="store_true", help="Run only hygiene + duplicate + policy gate.")
    parser.add_argument("--qa-only", action="store_true", help="Run only hygiene + duplicate + QA gate.")
    parser.add_argument("--e2e-only", action="store_true", help="Run only E2E pipeline gates (skip policy/sot/shard).")
    parser.add_argument("--source", choices=["local-run", "ci-run"], default="local-run")
    parser.add_argument("--report-bus", action="store_true", help="Append a single bus event to report_bus.jsonl.")
    args = parser.parse_args()

    exclusive = sum([args.policy_only, args.qa_only, args.e2e_only])
    if exclusive > 1:
        print("ERROR: --policy-only, --qa-only, --e2e-only are mutually exclusive.")
        return 2

    guard_mode = parse_guard_mode()
    if guard_mode == "off":
        print("INFO: SSID_GUARD_MODE=off — all guards skipped.")
        return 0
    if guard_mode != "soft":
        print(f"INFO: SSID_GUARD_MODE={guard_mode}")

    exit_code, failed_gate, gates_run = _execute_gate_chain(args, guard_mode)

    # Append exactly 1 bus event (PASS or FAIL) if --report-bus
    if args.report_bus:
        from report_bus import append_event, get_head_sha, make_event
        sha = get_head_sha(PROJECT_ROOT)
        severity = "info" if exit_code == 0 else "error"
        summary = f"Gate chain {'PASS' if exit_code == 0 else 'FAIL'}"
        if failed_gate:
            summary += f" at {failed_gate}"
        summary += f" ({gates_run} gates)"
        event = make_event(
            repo="SSID", sha=sha, source="verify_gate", kind="ops",
            severity=severity, summary=summary,
            payload={"exit_code": exit_code, "gates_run": gates_run, "failed_gate": failed_gate},
        )
        path = append_event(event)
        print(f"INFO: Bus event appended to {path}")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
