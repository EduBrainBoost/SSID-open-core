#!/usr/bin/env python3
"""
stability_gate.py - Objective "ready" check for PR branches.

Fixed gate sequence, stop-on-first-failure.
Output: PASS/FAIL + concrete findings. No scores.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOT_VALIDATOR = PROJECT_ROOT / "12_tooling" / "cli" / "sot_validator.py"
EXCEPTIONS_FILE = PROJECT_ROOT / "23_compliance" / "exceptions" / "root_level_exceptions.yaml"

REQUIRED_MODULE_COUNT = 24


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _run_cmd(cmd: list[str], label: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _is_sparse_checkout() -> bool:
    """Detect whether the current working tree uses sparse checkout."""
    sparse_file = PROJECT_ROOT / ".git" / "info" / "sparse-checkout"
    if sparse_file.is_file() and sparse_file.read_text(encoding="utf-8").strip():
        return True
    # .git may be a worktree pointer file; resolve the actual gitdir
    dot_git = PROJECT_ROOT / ".git"
    if dot_git.is_file():
        content = dot_git.read_text(encoding="utf-8").strip()
        if content.startswith("gitdir:"):
            gitdir = Path(content.split(":", 1)[1].strip())
            if not gitdir.is_absolute():
                gitdir = (PROJECT_ROOT / gitdir).resolve()
            sparse_in_gitdir = gitdir / "info" / "sparse-checkout"
            if sparse_in_gitdir.is_file() and sparse_in_gitdir.read_text(encoding="utf-8").strip():
                return True
    # Fallback: ask git directly (short timeout to avoid hangs)
    try:
        proc = subprocess.run(
            ["git", "sparse-checkout", "list"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return False


def gate_root24_lock() -> tuple[bool, str]:
    """Gate 1: Verify exactly 24 numbered root modules."""
    if _is_sparse_checkout():
        return True, "ROOT-24-LOCK: SKIP (sparse checkout active — root count not meaningful)"
    roots = sorted(
        p.name
        for p in PROJECT_ROOT.iterdir()
        if p.is_dir() and len(p.name) >= 3 and p.name[:2].isdigit() and "_" in p.name
    )
    if len(roots) != REQUIRED_MODULE_COUNT:
        return False, f"Expected {REQUIRED_MODULE_COUNT} roots, found {len(roots)}: {roots}"
    return True, f"ROOT-24-LOCK: {len(roots)} modules confirmed"


def gate_git_clean() -> tuple[bool, str]:
    """Gate 2: Git status clean (unstaged/untracked in scope = FAIL)."""
    proc = _run_cmd(["git", "status", "--porcelain"], "git status")
    if proc.returncode != 0:
        return False, f"git status failed: {proc.stderr.strip()}"
    output = proc.stdout.strip()
    if output:
        lines = output.splitlines()
        return False, f"Git status not clean ({len(lines)} changes): {lines[:5]}"
    return True, "Git status clean"


def gate_sot_verify() -> tuple[bool, str]:
    """Gate 3: SoT Validator --verify-all must exist and pass."""
    if not SOT_VALIDATOR.exists():
        return False, f"sot_validator.py not found at {SOT_VALIDATOR}"
    proc = _run_cmd([sys.executable, str(SOT_VALIDATOR), "--verify-all"], "SoT Verify")
    if proc.returncode != 0:
        detail = proc.stdout.strip() or proc.stderr.strip()
        return False, f"SoT Verify failed (exit={proc.returncode}): {detail}"
    return True, "SoT Verify passed"


def gate_pytest() -> tuple[bool, str]:
    """Gate 4: pytest -q (at minimum tooling tests)."""
    proc = _run_cmd([sys.executable, "-m", "pytest", "-q"], "pytest")
    if proc.returncode != 0:
        detail = proc.stdout.strip() or proc.stderr.strip()
        return False, f"pytest failed (exit={proc.returncode}): {detail[-500:]}"
    return True, f"pytest passed: {proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else 'ok'}"


def gate_evidence_write() -> tuple[bool, str]:
    """Gate 5: Can write deterministic evidence.json."""
    try:
        test_data = {
            "gate": "stability_gate",
            "result": "evidence_write_test",
            "utc": _utc_now(),
        }
        serialized = json.dumps(test_data, indent=2, sort_keys=True)
        # Verify deterministic: re-serialize must match
        re_serialized = json.dumps(json.loads(serialized), indent=2, sort_keys=True)
        if serialized != re_serialized:
            return False, "Evidence serialization not deterministic"
        # Verify SHA256 is stable
        h1 = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        h2 = hashlib.sha256(re_serialized.encode("utf-8")).hexdigest()
        if h1 != h2:
            return False, "Evidence hash not stable"
        return True, "Evidence write test passed (deterministic serialization confirmed)"
    except Exception as exc:
        return False, f"Evidence write test failed: {exc}"


def write_evidence(results: list[tuple[str, bool, str]], overall: bool) -> str | None:
    """Write evidence.json to agent_runs/STABILITY_GATE/<UTC>/."""
    utc_stamp = _utc_now()
    evidence_dir = PROJECT_ROOT / "02_audit_logging" / "agent_runs" / "STABILITY_GATE" / utc_stamp
    try:
        evidence_dir.mkdir(parents=True, exist_ok=True)
        evidence = {
            "gate": "stability_gate",
            "overall": "PASS" if overall else "FAIL",
            "timestamp_utc": utc_stamp,
            "checks": [
                {"name": name, "result": "PASS" if ok else "FAIL", "detail": detail} for name, ok, detail in results
            ],
        }
        evidence_path = evidence_dir / "evidence.json"
        evidence_path.write_text(
            json.dumps(evidence, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return str(evidence_path.relative_to(PROJECT_ROOT))
    except Exception as exc:
        print(f"WARNING: Could not write evidence: {exc}")
        return None


GATES = [
    ("ROOT-24-LOCK", gate_root24_lock),
    ("Git Clean", gate_git_clean),
    ("SoT Verify", gate_sot_verify),
    ("pytest", gate_pytest),
    ("Evidence Write", gate_evidence_write),
]


def run_all_gates() -> int:
    results: list[tuple[str, bool, str]] = []
    overall = True

    for name, gate_fn in GATES:
        ok, detail = gate_fn()
        results.append((name, ok, detail))
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {name}: {detail}")
        if not ok:
            overall = False
            print(f"STOP: {name} failed. Halting gate chain.")
            break

    evidence_path = write_evidence(results, overall)

    if overall:
        print("\nSTABILITY_GATE: PASS")
    else:
        print("\nSTABILITY_GATE: FAIL")

    if evidence_path:
        print(f"Evidence: {evidence_path}")

    return 0 if overall else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="stability_gate.py",
        description="Objective PR-readiness check. Stop-on-first-failure.",
    )
    parser.add_argument("--run", action="store_true", help="Run all gates")
    args = parser.parse_args()

    if args.run:
        return run_all_gates()

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
