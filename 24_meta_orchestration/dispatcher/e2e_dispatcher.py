#!/usr/bin/env python3
"""
SSID Consolidated Dispatcher v4.1
NON-INTERACTIVE, SAFE-FIX, ROOT-24-LOCK, SHA256-geloggt
"""
from __future__ import annotations

import argparse
import datetime as dt
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "12_tooling" / "scripts"
CLI_DIR = REPO_ROOT / "12_tooling" / "cli"
sys.path.insert(0, str(SCRIPTS_DIR))
from deterministic_repo_setup import move_to_worm
# CLI_DIR added AFTER deterministic_repo_setup import (naming collision in cli/)
if str(CLI_DIR) not in sys.path:
    sys.path.insert(0, str(CLI_DIR))
from _lib.run_id import compute_run_id, get_git_sha, compute_file_sha256
from _lib.shards import parse_yaml as _parse_yaml_file

# Sandbox outside repo to prevent self-inflation
_STATE_DIR = Path(os.environ.get("SSID_EMS_STATE_DIR", str(Path.home() / "Documents" / "SSID_EMS_STATE")))
SANDBOX_ROOT = _STATE_DIR / "sandboxes"
RUN_LEDGER_ROOT = REPO_ROOT / "02_audit_logging" / "agent_runs"
QUEUE_STATUS_FILE = REPO_ROOT / "24_meta_orchestration" / "queue" / "TASK_QUEUE.status.jsonl"

RUN_ALL_GATES = REPO_ROOT / "12_tooling" / "cli" / "run_all_gates.py"
SOT_VALIDATOR = REPO_ROOT / "12_tooling" / "cli" / "sot_validator.py"
QA_MASTER = REPO_ROOT / "02_audit_logging" / "archives" / "qa_master_suite" / "qa_master_suite.py"
QA_FALLBACK = REPO_ROOT / "11_test_simulation" / "tests_compliance" / "test_sot_validator.py"
DUPLICATE_GUARD = REPO_ROOT / "12_tooling" / "cli" / "duplicate_guard.py"
GITIGNORE = REPO_ROOT / ".gitignore"

EXCLUDED_COPY_TOP = {
    ".git", ".ssid_sandbox", ".claude", ".pytest_cache", "__pycache__",
}
# Directories excluded recursively during copytree
EXCLUDED_COPY_RECURSIVE = {
    "node_modules", "dist", ".next", "build", "coverage", "tmp",
    ".pytest_cache", "__pycache__", ".git", ".ssid_sandbox",
}
EXCLUDED_SNAPSHOT_PARTS = EXCLUDED_COPY_TOP | EXCLUDED_COPY_RECURSIVE

# Infrastructure paths always allowed in write gate (not subject to allowlist)
WRITE_GATE_BYPASS_PREFIXES = {".claude/", ".github/"}


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    scope: Dict[str, Any]
    allowed_paths: List[str]
    expected_artifacts: List[str]
    acceptance_checks: List[str]
    agent_role: str
    agent_roles: List[str]
    patch_strategy: str
    log_mode: str
    prompt: str
    tool_name: str
    health_check: bool = False
    resolved_worker: Optional[dict] = None


@dataclass(frozen=True)
class QueueDefaults:
    no_new_files: bool
    max_changed_files: int
    max_changed_lines: int
    stop_on_fail_count: int
    acceptance_checks: List[str]


@dataclass(frozen=True)
class QueueTask:
    task_id: str
    scope: str
    allowed_paths: List[str]
    expected_artifacts: List[str]
    acceptance_checks: List[str]
    no_new_files: bool
    max_changed_files: int
    max_changed_lines: int
    stop_failures: int
    stop_on_missing_files: bool
    notes: str
    allow_new_files_list: List[str]
    worker_command: Optional[List[str]]
    worker_type: Optional[str] = None
    health_check: bool = False


def _is_health_check_prompt(prompt: str) -> bool:
    """Detect health-check / echo-test prompts by keyword."""
    lower = prompt.lower()
    return any(kw in lower for kw in ("health check", "echo test", "verify", "return pass"))


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _duration_seconds(start: str, end: str) -> float:
    s = dt.datetime.fromisoformat(start.replace("Z", "+00:00"))
    e = dt.datetime.fromisoformat(end.replace("Z", "+00:00"))
    return (e - s).total_seconds()


def _norm_rel(path: str) -> str:
    return path.replace("\\", "/").strip("/")


def _allowed(rel: str, allowed_paths: Sequence[str]) -> bool:
    rel_norm = _norm_rel(rel)
    for raw in allowed_paths:
        base = _norm_rel(raw)
        if not base:
            continue
        if rel_norm == base or rel_norm.startswith(base + "/"):
            return True
    return False


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


_TASK_ID_RE = re.compile(r'^[A-Za-z0-9._-]{1,128}$')
_SUBTASK_SEPARATOR = '--'


def _validate_task_id(task_id: str) -> str:
    """Validate task_id (including subtask IDs with -- separator)."""
    if not _TASK_ID_RE.match(task_id):
        raise SystemExit(f"FAIL: invalid task_id: {task_id!r}")
    if '..' in task_id or '/' in task_id or '\\' in task_id:
        raise SystemExit(f"FAIL: path traversal in task_id: {task_id!r}")
    return task_id


def _parse_subtask_id(task_id: str) -> tuple:
    """Parse subtask ID into (parent_id, agent_suffix) or (task_id, None) if not a subtask."""
    _validate_task_id(task_id)
    if _SUBTASK_SEPARATOR in task_id:
        parts = task_id.split(_SUBTASK_SEPARATOR, 1)
        return parts[0], parts[1]
    return task_id, None


def _read_text_or_none(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None


def _ensure_gitignore_has_sandbox() -> None:
    if not GITIGNORE.exists():
        raise SystemExit("FAIL: .gitignore missing")
    # Sandbox is now outside repo, but keep backward compatibility check
    lines = GITIGNORE.read_text(encoding="utf-8", errors="replace").splitlines()
    stripped = {ln.strip() for ln in lines}
    if ".ssid_sandbox/" not in stripped:
        # Warn but don't block - sandbox may be outside repo
        print("WARN: .gitignore missing '.ssid_sandbox/' entry")


def _iter_files(root: Path) -> Iterable[Path]:
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if any(part in EXCLUDED_SNAPSHOT_PARTS for part in p.parts):
            continue
        yield p


def _snapshot(root: Path) -> Dict[str, str]:
    snap: Dict[str, str] = {}
    for p in _iter_files(root):
        rel = _norm_rel(p.relative_to(root).as_posix())
        digest = hashlib.sha256(p.read_bytes()).hexdigest()
        snap[rel] = digest
    return snap


def _collect_changes(repo_root: Path, sandbox: Path) -> Tuple[List[str], List[str], List[str]]:
    base = _snapshot(repo_root)
    sbx = _snapshot(sandbox)
    all_paths = sorted(set(base.keys()) | set(sbx.keys()))

    changed: List[str] = []
    created: List[str] = []
    deleted: List[str] = []
    for rel in all_paths:
        b = base.get(rel)
        s = sbx.get(rel)
        if b == s:
            continue
        changed.append(rel)
        if b is None and s is not None:
            created.append(rel)
        if b is not None and s is None:
            deleted.append(rel)
    return changed, created, deleted


def _build_patch(repo_root: Path, sandbox: Path, changed_paths: Sequence[str]) -> Tuple[str, int]:
    chunks: List[str] = []
    changed_lines = 0

    for rel in sorted(set(changed_paths)):
        left = repo_root / rel
        right = sandbox / rel
        left_exists = left.exists()
        right_exists = right.exists()
        left_text = _read_text_or_none(left) if left_exists else ""
        right_text = _read_text_or_none(right) if right_exists else ""
        if left_exists and left_text is None:
            print(f"SKIP_BINARY: {rel}")
            continue
        if right_exists and right_text is None:
            print(f"SKIP_BINARY: {rel}")
            continue

        from_file = "a/" + rel if left_exists else "/dev/null"
        to_file = "b/" + rel if right_exists else "/dev/null"
        diff = list(
            difflib.unified_diff(
                (left_text or "").splitlines(keepends=True),
                (right_text or "").splitlines(keepends=True),
                fromfile=from_file,
                tofile=to_file,
                n=3,
            )
        )
        for line in diff:
            if line.startswith("+++ ") or line.startswith("--- "):
                continue
            if line.startswith("+") or line.startswith("-"):
                changed_lines += 1
        if diff:
            chunks.extend(diff)
    patch = "".join(chunks)
    return patch, changed_lines


def _run_cmd(cmd: List[str], cwd: Path, env: Optional[Dict[str, str]] = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )


def _run_duplicate_guard(target_root: Path) -> int:
    guard_path = target_root / DUPLICATE_GUARD.relative_to(REPO_ROOT)
    proc = _run_cmd([sys.executable, str(guard_path), "--repo-root", str(target_root)], cwd=target_root)
    return proc.returncode


def _run_single_gate(task_root: Path, gate: str) -> int:
    env = dict(os.environ)
    env["SSID_ACTIVE_RUN"] = "1"

    run_all_gates = task_root / RUN_ALL_GATES.relative_to(REPO_ROOT)
    sot_validator = task_root / SOT_VALIDATOR.relative_to(REPO_ROOT)
    qa_master = task_root / QA_MASTER.relative_to(REPO_ROOT)
    qa_fallback = task_root / QA_FALLBACK.relative_to(REPO_ROOT)

    if gate == "policy":
        cmd = [sys.executable, str(run_all_gates), "--policy-only"]
    elif gate == "sot":
        cmd = [sys.executable, str(sot_validator), "--verify-all"]
    elif gate == "qa":
        if qa_master.exists():
            cmd = [sys.executable, str(qa_master), "--mode", "minimal"]
        elif qa_fallback.exists():
            cmd = [sys.executable, "-m", "pytest", "-q", str(qa_fallback)]
        else:
            return 1
    else:
        return 1
    proc = _run_cmd(cmd, cwd=task_root, env=env)
    return proc.returncode


def _write_manifest(
    run_id: str,
    task: QueueTask,
    started: str,
    ended: str,
    changed_files: List[str],
    patch_text: str,
    gates: Dict[str, str],
    exit_codes: Dict[str, int],
    tool_name: str,
    save_patch: bool,
) -> None:
    out_dir = RUN_LEDGER_ROOT / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    patch_sha = _sha256_text(patch_text)
    if save_patch:
        (out_dir / "patch.diff").write_text(patch_text, encoding="utf-8")

    manifest = {
        "run_id": run_id,
        "task_id": task.task_id,
        "timestamp_start": started,
        "timestamp_end": ended,
        "durations": {"seconds": _duration_seconds(started, ended)},
        "tool_name": tool_name or "unknown",
        "changed_files": changed_files,
        "patch_sha256": patch_sha,
        "gates": gates,
        "exit_codes": exit_codes,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    # NC-2/INC-1 fix: Preserve essential evidence files, do not delete them.
    allowed_names = {
        "manifest.json", 
        "patch.diff",
        "GATE_RUN_REPORT.json",
        "SHARDS_PROMOTION_QA_REPORT.json",
    }
    if not save_patch:
        allowed_names.remove("patch.diff")

    # This loop is now for future-proofing, to remove any truly unexpected files.
    # The primary evidence files are now preserved.
    for p in out_dir.iterdir():
        if p.name not in allowed_names and p.is_file():
            # Instead of deleting, move to a 'retained' area for audit.
            retained_dir = out_dir / "retained_unexpected"
            retained_dir.mkdir(exist_ok=True)
            shutil.move(str(p), str(retained_dir / p.name))


def _append_queue_status(run_id: str, task: QueueTask, status: str, gates: Dict[str, str], message: str) -> None:
    QUEUE_STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": _utc_now(),
        "run_id": run_id,
        "task_id": task.task_id,
        "status": status,
        "gates": gates,
        "message": message,
    }
    with QUEUE_STATUS_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")


def _load_task_spec(task_path: Path) -> TaskSpec:
    data = yaml.safe_load(task_path.read_text(encoding="utf-8")) if task_path.suffix.lower() in {".yml", ".yaml"} else json.loads(task_path.read_text(encoding="utf-8"))
    return TaskSpec(
        task_id=str(data["task_id"]),
        scope=data.get("scope", {}) or {},
        allowed_paths=list(data["allowed_paths"]),
        expected_artifacts=list(data.get("expected_artifacts", [])),
        acceptance_checks=list(data.get("acceptance_checks", ["policy", "sot", "qa"])),
        agent_role=str(data.get("agent_role", "Implementer")),
        agent_roles=list(data.get("agent_roles", [data.get("agent_role", "Implementer")])),
        patch_strategy=str(data.get("patch_strategy", "single-commit")),
        log_mode=str(data.get("log_mode", "MINIMAL")),
        prompt=str(data.get("prompt", "")),
        tool_name=str(data.get("tool_name", "unknown")),
        health_check=bool(data.get("health_check", False)),
        resolved_worker=data.get("resolved_worker", None),
    )


def _copy_repo_to_sandbox(sandbox_root: Path) -> None:
    if sandbox_root.exists():
        move_to_worm(sandbox_root, reason="sandbox_recreation")
    sandbox_root.mkdir(parents=True, exist_ok=True)
    print(f"PHASE: materialize")
    print(f"SANDBOX_TARGET: {sandbox_root.as_posix()}")
    items = sorted(REPO_ROOT.iterdir(), key=lambda p: p.name)
    total = len([i for i in items if i.name not in EXCLUDED_COPY_TOP])
    copied = 0
    for item in items:
        if item.name in EXCLUDED_COPY_TOP:
            print(f"SKIP: {item.name}")
            continue
        dest = sandbox_root / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns(*EXCLUDED_COPY_RECURSIVE))
        elif item.is_file():
            shutil.copy2(item, dest)
        copied += 1
        print(f"COPY: {item.name} ({copied}/{total})")
    print(f"PHASE: materialize_done ({copied} items)")


def _enforce_write_gate(
    task: QueueTask,
    changed: Sequence[str],
    created: Sequence[str],
    changed_files_count: int,
    changed_lines_count: int,
) -> None:
    outside = [p for p in changed
               if not _allowed(p, task.allowed_paths)
               and not any(p.startswith(bp) for bp in WRITE_GATE_BYPASS_PREFIXES)]
    if outside:
        raise SystemExit(f"WRITE_GATE_FAIL: path outside allowlist: {outside[0]}")

    if task.no_new_files:
        illegal_new = []
        for p in created:
            if p in task.allow_new_files_list:
                continue
            illegal_new.append(p)
        if illegal_new:
            raise SystemExit(f"WRITE_GATE_FAIL: new files not allowed: {illegal_new[0]}")

    if changed_files_count > task.max_changed_files:
        raise SystemExit(f"WRITE_GATE_FAIL: max_changed_files exceeded ({changed_files_count}>{task.max_changed_files})")
    if changed_lines_count > task.max_changed_lines:
        raise SystemExit(f"WRITE_GATE_FAIL: max_changed_lines exceeded ({changed_lines_count}>{task.max_changed_lines})")


def _parse_queue(path: Path) -> Tuple[QueueDefaults, List[QueueTask]]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if str(raw.get("version")) != "1.0":
        raise SystemExit("FAIL: queue version must be '1.0'")
    d = raw.get("defaults", {}) or {}
    defaults = QueueDefaults(
        no_new_files=bool(d.get("no_new_files", True)),
        max_changed_files=int(d.get("max_changed_files", 10)),
        max_changed_lines=int(d.get("max_changed_lines", 400)),
        stop_on_fail_count=int(d.get("stop_on_fail_count", 1)),
        acceptance_checks=[str(x) for x in d.get("acceptance_checks", ["policy", "sot", "qa"])],
    )

    seen: set[str] = set()
    tasks: List[QueueTask] = []
    for t in raw.get("tasks", []) or []:
        task_id = str(t["task_id"])
        _validate_task_id(task_id)
        if task_id in seen:
            raise SystemExit(f"FAIL: duplicate task_id in queue: {task_id}")
        seen.add(task_id)
        max_changes = t.get("max_changes", {}) or {}
        stop_conditions = t.get("stop_conditions", {}) or {}
        worker_command = t.get("worker_command")
        if isinstance(worker_command, str):
            worker_command = worker_command.split()
        # Resolve worker_type from resolved_worker or direct field
        resolved_worker = t.get("resolved_worker") or {}
        worker_type = str(resolved_worker.get("worker_type")) if resolved_worker.get("worker_type") else t.get("worker_type")
        tasks.append(
            QueueTask(
                task_id=task_id,
                scope=str(t.get("scope", "root")),
                allowed_paths=[str(x) for x in t.get("allowed_paths", [])],
                expected_artifacts=[str(x) for x in t.get("expected_artifacts", [])],
                acceptance_checks=[str(x) for x in t.get("acceptance_checks", defaults.acceptance_checks)],
                no_new_files=bool(t.get("no_new_files", defaults.no_new_files)),
                max_changed_files=int(max_changes.get("files", defaults.max_changed_files)),
                max_changed_lines=int(max_changes.get("lines", defaults.max_changed_lines)),
                stop_failures=int(stop_conditions.get("failures", defaults.stop_on_fail_count)),
                stop_on_missing_files=bool(stop_conditions.get("on_missing_files", False)),
                notes=str(t.get("notes", "")),
                allow_new_files_list=[str(x) for x in t.get("allow_new_files_list", [])],
                worker_command=worker_command if isinstance(worker_command, list) else None,
                worker_type=worker_type,
            )
        )
    return defaults, tasks


def _run_queue_task(task: QueueTask, keep_sandbox_on_fail: bool, save_patch: bool) -> Tuple[str, bool]:
    _validate_task_id(task.task_id)
    started = _utc_now()
    run_id = f"{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{task.task_id}_{uuid.uuid4().hex[:8]}"
    sandbox = SANDBOX_ROOT / run_id / task.task_id

    _copy_repo_to_sandbox(sandbox)
    print(f"TASK_START: {task.task_id}")
    print(f"SANDBOX: {sandbox.as_posix()}")
    # Resolve worker type for type-specific execution
    wtype = task.worker_type

    if task.worker_command:
        if wtype == "noop":
            print("NOOP_WORKER: skipping execution (noop worker type)")
        elif wtype == "shell_command":
            print(f"SHELL_WORKER: executing shell command")
            proc = _run_cmd(task.worker_command, cwd=sandbox)
            if proc.returncode != 0:
                print(f"SHELL_WORKER_FAIL: exit={proc.returncode}")
                if proc.stderr:
                    print(f"  STDERR: {proc.stderr[:500]}")
        elif wtype == "python_script":
            print(f"PYTHON_WORKER: executing script")
            proc = _run_cmd(task.worker_command, cwd=sandbox)
            if proc.returncode != 0:
                print(f"PYTHON_WORKER_FAIL: exit={proc.returncode}")
                if proc.stderr:
                    print(f"  STDERR: {proc.stderr[:500]}")
        elif wtype == "claude_agent":
            print(f"CLAUDE_WORKER: executing claude agent")
            _run_cmd(task.worker_command, cwd=sandbox)
        else:
            print(f"GENERIC_WORKER: executing command (type={wtype})")
            _run_cmd(task.worker_command, cwd=sandbox)
    else:
        print("MANUAL_PATCH_MODE: no worker_command resolved (resolved_worker absent or noop)")
        print(f"HINT: apply changes in sandbox only -> {sandbox.as_posix()}")

    # Health-check mode: no worker + no expected changes = immediate PASS
    is_health_check = not task.worker_command and task.health_check

    # Health-check fast path: skip expensive snapshot/diff entirely
    if is_health_check:
        print("HEALTH_CHECK: no worker, no changes expected -> PASS")
        ended = _utc_now()
        gates = {"policy": "SKIP", "sot": "SKIP", "qa": "SKIP"}
        exits = {"policy": 0, "sot": 0, "qa": 0}
        _write_manifest(run_id, task, started, ended, [], "", gates, exits, "health_check", save_patch)
        _append_queue_status(run_id, task, "PASS", gates, "health_check: no worker, no changes")
        root_run_dir = SANDBOX_ROOT / run_id
        if root_run_dir.exists():
            move_to_worm(root_run_dir, reason="health_check_cleanup")
        return run_id, True

    if task.stop_on_missing_files:
        missing = [p for p in task.allowed_paths if not (sandbox / p).exists()]
        if missing:
            raise SystemExit(f"TASK_FAIL: missing required path(s): {missing[0]}")

    changed, created, _deleted = _collect_changes(REPO_ROOT, sandbox)
    patch_text, changed_lines = _build_patch(REPO_ROOT, sandbox, changed)
    _enforce_write_gate(task, changed, created, len(changed), changed_lines)

    duplicate_rc = _run_duplicate_guard(sandbox)
    if duplicate_rc != 0:
        gates = {"policy": "FAIL", "sot": "FAIL", "qa": "FAIL"}
        exits = {"duplicate_guard": duplicate_rc, "policy": 1, "sot": 1, "qa": 1}
        ended = _utc_now()
        _write_manifest(run_id, task, started, ended, changed, patch_text, gates, exits, "unknown", save_patch)
        _append_queue_status(run_id, task, "FAIL", gates, "duplicate guard failed")
        return run_id, False

    gate_results: Dict[str, str] = {"policy": "PASS", "sot": "PASS", "qa": "PASS"}
    exit_codes: Dict[str, int] = {"duplicate_guard": 0, "policy": 0, "sot": 0, "qa": 0}
    for gate in task.acceptance_checks:
        if gate not in {"policy", "sot", "qa"}:
            continue
        code = _run_single_gate(sandbox, gate)
        exit_codes[gate] = code
        if code != 0:
            gate_results[gate] = "FAIL"
            for rest in ("policy", "sot", "qa"):
                if rest not in task.acceptance_checks:
                    continue
                if rest != gate and exit_codes[rest] == 0:
                    gate_results[rest] = "FAIL"
            break

    success = all(gate_results[g] == "PASS" for g in task.acceptance_checks if g in gate_results)
    if success and patch_text.strip():
        apply_proc = subprocess.run(
            ["git", "apply", "--whitespace=nowarn", "-"],
            cwd=str(REPO_ROOT),
            input=patch_text,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
        )
        exit_codes["apply_patch"] = apply_proc.returncode
        if apply_proc.returncode != 0:
            success = False

    ended = _utc_now()
    _write_manifest(run_id, task, started, ended, changed, patch_text, gate_results, exit_codes, "unknown", save_patch)
    _append_queue_status(run_id, task, "PASS" if success else "FAIL", gate_results, "completed")

    if success or not keep_sandbox_on_fail:
        root_run_dir = SANDBOX_ROOT / run_id
        if root_run_dir.exists():
            move_to_worm(root_run_dir, reason="task_run_cleanup")
    return run_id, success


def handle_run_queue(args: argparse.Namespace) -> int:
    _ensure_gitignore_has_sandbox()
    queue_path = Path(args.queue).resolve()
    _, tasks = _parse_queue(queue_path)
    fail_count = 0

    for task in tasks:
        try:
            _run_id, ok = _run_queue_task(task, keep_sandbox_on_fail=args.keep_sandbox_on_fail, save_patch=args.save_patch)
        except SystemExit as exc:
            print(str(exc))
            ok = False
        if not ok:
            fail_count += 1
            if fail_count >= task.stop_failures:
                print("QUEUE_STOP: stop_on_fail_count reached")
                return 24
    return 0


def handle_run(args: argparse.Namespace) -> int:
    task_id = args.task_id or uuid.uuid4().hex[:12]
    _validate_task_id(task_id)
    sandbox = SANDBOX_ROOT / task_id
    _copy_repo_to_sandbox(sandbox)
    print(f"TASK_START: {task_id}")
    print(f"SANDBOX: {sandbox.as_posix()}")
    print("SANDBOX_READY")
    return 0


def handle_package(args: argparse.Namespace) -> int:
    spec = _load_task_spec(Path(args.task))
    health_check = getattr(spec, 'health_check', False) or _is_health_check_prompt(spec.prompt)

    # Resolve worker command and type from task spec
    worker_command = None
    worker_type = None
    if spec.resolved_worker:
        if spec.resolved_worker.get("worker_command"):
            worker_command = spec.resolved_worker["worker_command"]
        if spec.resolved_worker.get("worker_type"):
            worker_type = str(spec.resolved_worker["worker_type"])

    task = QueueTask(
        task_id=spec.task_id,
        scope="root",
        allowed_paths=spec.allowed_paths,
        expected_artifacts=spec.expected_artifacts,
        acceptance_checks=spec.acceptance_checks,
        no_new_files=True,
        max_changed_files=500,
        max_changed_lines=20000,
        stop_failures=1,
        stop_on_missing_files=False,
        notes="package compatibility mode",
        allow_new_files_list=[],
        worker_command=worker_command,
        worker_type=worker_type,
        health_check=health_check,
    )
    _run_id, ok = _run_queue_task(task, keep_sandbox_on_fail=False, save_patch=True)
    return 0 if ok else 24


REPORTS_DIR = REPO_ROOT / "02_audit_logging" / "reports"
SHARDS_REGISTRY = REPO_ROOT / "24_meta_orchestration" / "registry" / "shards_registry.json"
CONFORMANCE_GATE = REPO_ROOT / "12_tooling" / "cli" / "shard_conformance_gate.py"


def _e2e_log_event(log_lines: list, run_id: str, event: str, detail: str = "") -> None:
    entry = {
        "ts_utc": _utc_now(),
        "run_id": run_id,
        "event": event,
    }
    if detail:
        entry["detail"] = detail
    log_lines.append(json.dumps(entry, sort_keys=True))


def handle_run_task(args: argparse.Namespace) -> int:
    """E2E Pipeline: load task -> resolve shard -> validate contracts -> emit reports."""
    import jsonschema  # noqa: local import to keep module-level deps light

    task_path = Path(args.task).resolve()
    if not task_path.exists():
        print(f"ERROR: Task file not found: {task_path}")
        return 2

    task_data = yaml.safe_load(task_path.read_text(encoding="utf-8"))
    required_fields = ["task_id", "root_id", "shard_id", "action", "inputs_hash_ref"]
    missing = [f for f in required_fields if f not in task_data]
    if missing:
        print(f"ERROR: Task YAML missing fields: {missing}")
        return 2

    task_id = str(task_data["task_id"])
    root_id = str(task_data["root_id"])
    shard_id = str(task_data["shard_id"])
    action = str(task_data["action"])
    inputs_ref = str(task_data["inputs_hash_ref"])

    # Load inputs descriptor
    inputs_path = REPO_ROOT / inputs_ref
    if not inputs_path.exists():
        print(f"ERROR: Inputs descriptor not found: {inputs_path}")
        return 2
    inputs_data = json.loads(inputs_path.read_text(encoding="utf-8"))
    inputs_hash = str(inputs_data.get("content_hash", ""))

    # Compute deterministic run_id
    try:
        git_sha = get_git_sha(REPO_ROOT)
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        return 2

    run_id = compute_run_id(git_sha, task_id, root_id, shard_id, action, inputs_hash)
    log_lines: list[str] = []
    _e2e_log_event(log_lines, run_id, "TASK_RECEIVED", f"task_id={task_id}")

    # Load shards registry
    if not SHARDS_REGISTRY.exists():
        print(f"ERROR: Shards registry not found: {SHARDS_REGISTRY}")
        _e2e_log_event(log_lines, run_id, "ERROR", "shards_registry.json missing")
        return 2

    registry = json.loads(SHARDS_REGISTRY.read_text(encoding="utf-8"))
    shard_entry = None
    for s in registry.get("shards", []):
        if s["root_id"] == root_id and s["shard_id"] == shard_id:
            shard_entry = s
            break

    if shard_entry is None:
        print(f"ERROR: Shard {root_id}/{shard_id} not found in registry")
        _e2e_log_event(log_lines, run_id, "ERROR", f"shard {root_id}/{shard_id} not in registry")
        return 2

    _e2e_log_event(log_lines, run_id, "ROUTE_RESOLVED",
                   f"shard={root_id}/{shard_id} tier={shard_entry.get('promotion_tier')}")

    # Validate entrypoint matches action
    entrypoints = shard_entry.get("entrypoints", [])
    matching = [e for e in entrypoints if e.get("kind") == action]
    if not matching and action == "contract_validate":
        # Fallback: use contracts_index_path directly
        cip = shard_entry.get("contracts_index_path")
        if cip:
            matching = [{"kind": "contract_validate", "target": cip}]

    if not matching:
        print(f"ERROR: No entrypoint for action '{action}' in shard {root_id}/{shard_id}")
        _e2e_log_event(log_lines, run_id, "ERROR", f"no entrypoint for action={action}")
        return 2

    # Execute contract_validate
    violations: list[str] = []
    _e2e_log_event(log_lines, run_id, "SHARD_STARTED", f"action={action}")

    contracts_index_path = REPO_ROOT / matching[0]["target"]
    if not contracts_index_path.exists():
        violations.append(f"contracts/index.yaml missing at {matching[0]['target']}")
    else:
        ci_data = _parse_yaml_file(contracts_index_path)
        if ci_data is None:
            violations.append("contracts/index.yaml not parseable")
        else:
            specs = ci_data.get("specs", [])
            for spec in specs:
                spec_path = contracts_index_path.parent / spec["path"]
                if not spec_path.exists():
                    violations.append(f"Contract spec missing: {spec['path']}")
                    continue
                try:
                    schema = json.loads(spec_path.read_text(encoding="utf-8"))
                    jsonschema.validators.validator_for(schema).check_schema(schema)
                except json.JSONDecodeError as exc:
                    violations.append(f"JSON parse error in {spec['path']}: {exc}")
                except jsonschema.SchemaError as exc:
                    violations.append(f"Schema error in {spec['path']}: {exc.message}")

    # Run conformance gate if conformance index exists
    conf_index_path = shard_entry.get("conformance_index_path")
    if conf_index_path and (REPO_ROOT / conf_index_path).exists():
        proc = subprocess.run(
            [sys.executable, str(CONFORMANCE_GATE), "--root", root_id, "--shard", shard_id],
            cwd=str(REPO_ROOT),
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if proc.returncode != 0:
            violations.append(f"Conformance gate FAIL (exit={proc.returncode}): {proc.stdout.strip()}")

    started_utc = _utc_now()
    status = "PASS" if len(violations) == 0 else "FAIL"
    _e2e_log_event(log_lines, run_id, "SHARD_FINISHED", f"status={status} violations={len(violations)}")

    # Collect artifact hashes
    artifact_hashes = []
    hash_targets = [
        ("shards_registry", str(SHARDS_REGISTRY.relative_to(REPO_ROOT)), "registry"),
        ("task_yaml", str(task_path.relative_to(REPO_ROOT)), "task"),
        ("inputs_json", inputs_ref, "input"),
    ]
    if contracts_index_path.exists():
        hash_targets.append(("contracts_index", matching[0]["target"], "index"))
    ci_data_for_hashes = _parse_yaml_file(contracts_index_path) if contracts_index_path.exists() else None
    if ci_data_for_hashes:
        for spec in ci_data_for_hashes.get("specs", []):
            sp = contracts_index_path.parent / spec["path"]
            if sp.exists():
                hash_targets.append(("contract_spec", str(sp.relative_to(REPO_ROOT)), "contract"))

    for name, rel_path, kind in hash_targets:
        abs_path = REPO_ROOT / rel_path
        if abs_path.exists():
            artifact_hashes.append({
                "path": rel_path.replace("\\", "/"),
                "sha256": compute_file_sha256(abs_path),
                "kind": kind,
            })

    # Build reports
    e2e_run_report = {
        "schema_version": "1.0.0",
        "run_id": run_id,
        "source": args.source,
        "git_sha": git_sha,
        "task": {
            "task_id": task_id,
            "root_id": root_id,
            "shard_id": shard_id,
            "action": action,
            "inputs_hash": inputs_hash,
        },
        "resolved": {
            "shard_key": f"{root_id}/{shard_id}",
            "promotion_tier": shard_entry.get("promotion_tier"),
            "contracts_index": matching[0]["target"],
        },
        "hashes": {a["path"]: a["sha256"] for a in artifact_hashes},
        "timing": {
            "finished_utc": started_utc,
        },
        "status": status,
        "violations": violations,
    }

    e2e_hashes_report = {
        "schema_version": "1.0.0",
        "run_id": run_id,
        "git_sha": git_sha,
        "artifacts": artifact_hashes,
    }

    # Write reports
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    e2e_run_path = REPORTS_DIR / f"E2E_RUN_{run_id}.json"
    e2e_run_path.write_text(
        json.dumps(e2e_run_report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    _e2e_log_event(log_lines, run_id, "REPORT_WRITTEN", f"E2E_RUN_{run_id}.json")

    run_log_path = REPORTS_DIR / f"RUN_LOG_{run_id}.jsonl"
    run_log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")

    hashes_path = REPORTS_DIR / f"E2E_ARTIFACT_HASHES_{run_id}.json"
    hashes_path.write_text(
        json.dumps(e2e_hashes_report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"{status}: run_id={run_id}")
    print(f"  E2E_RUN: {e2e_run_path.relative_to(REPO_ROOT)}")
    print(f"  RUN_LOG: {run_log_path.relative_to(REPO_ROOT)}")
    print(f"  HASHES:  {hashes_path.relative_to(REPO_ROOT)}")
    if violations:
        for v in violations:
            print(f"  VIOLATION: {v}")

    return 0 if status == "PASS" else 1


def handle_gates(args: argparse.Namespace) -> int:
    _ensure_gitignore_has_sandbox()
    root = Path(args.sandbox).resolve() if args.sandbox else REPO_ROOT
    if _run_duplicate_guard(root) != 0:
        return 1
    for gate in ["policy", "sot", "qa"]:
        if _run_single_gate(root, gate) != 0:
            return 1
    print("GATES_PASSED")
    return 0


def handle_run_profile(args: argparse.Namespace) -> int:
    """SSIDCTL v2: run an activation profile through the full runtime pipeline."""
    meta_orch = REPO_ROOT / "24_meta_orchestration"
    if str(meta_orch) not in sys.path:
        sys.path.insert(0, str(meta_orch))
    from runtime.runner import SSIDCTLRunner
    runner = SSIDCTLRunner(repo_root=REPO_ROOT, dry_run=args.dry_run)
    return runner.run(args.profile)


def main() -> int:
    parser = argparse.ArgumentParser(description="SSID Consolidated Dispatcher v4.1 - single entry point")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Prepare sandbox for manual worker run")
    run_p.add_argument("--task-id", help="Task id (optional)")

    package_p = sub.add_parser("package", help="Compatibility mode: task spec -> run once")
    package_p.add_argument("--task", required=True, help="Path to task spec yaml/json")

    gates_p = sub.add_parser("gates", help="Run duplicate guard + policy + sot + qa")
    gates_p.add_argument("--sandbox", help="Optional root path for gate execution")

    queue_p = sub.add_parser("run-queue", help="Run deterministic task queue")
    queue_p.add_argument("queue", help="Path to TASK_QUEUE.yaml")
    queue_p.add_argument("--keep-sandbox-on-fail", action="store_true", help="Do not clean failed task sandbox")
    queue_p.add_argument("--save-patch", action="store_true", help="Persist patch.diff next to manifest")

    e2e_p = sub.add_parser("run-task", help="E2E pipeline: task -> dispatcher -> shard -> reports")
    e2e_p.add_argument("--task", required=True, help="Path to task YAML")
    e2e_p.add_argument("--source", choices=["local-run", "ci-run"], default="local-run")
    e2e_p.add_argument("--deterministic", action="store_true", help="Stable output (no volatile timestamps)")

    # SSIDCTL v2 runtime entry point
    profile_p = sub.add_parser("run-profile", help="SSIDCTL v2: run activation profile")
    profile_p.add_argument("--profile", required=True, help="Activation profile ID (e.g. gate55_core_11)")
    profile_p.add_argument("--dry-run", action="store_true", help="Validate without execution")

    args = parser.parse_args()

    if args.command == "run":
        return handle_run(args)
    if args.command == "package":
        return handle_package(args)
    if args.command == "gates":
        return handle_gates(args)
    if args.command == "run-queue":
        return handle_run_queue(args)
    if args.command == "run-task":
        return handle_run_task(args)
    if args.command == "run-profile":
        return handle_run_profile(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
