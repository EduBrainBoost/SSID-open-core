#!/usr/bin/env python3
"""
automation_loop.py - Deterministic TaskSpec-driven run framework.

Subcommands:
  --verify-spec --spec <path>   Validate TaskSpec YAML schema
  --init                        Ensure audit directories exist
  --start --task <ID> --spec <path>  Initialize an agent run
  --finalize --task <ID>        Run checks, produce evidence, create WORM ZIP
  --smoke-e2e                   Run full start->edit->finalize smoke test

Exit codes:
  0  EXIT_SUCCESS        Command completed successfully
  1  EXIT_GATE_FAILURE   A gate check or validation failed
  2  EXIT_SPEC_INVALID   Spec file missing or structurally invalid
  3  EXIT_TOOLING_ERROR  CLI usage error (missing required arguments)

PR-only, no secrets, no scores. PASS/FAIL + findings only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
AGENT_RUNS_DIR = PROJECT_ROOT / "02_audit_logging" / "agent_runs"
REPORTS_DIR = PROJECT_ROOT / "02_audit_logging" / "reports"
WORM_BASE = PROJECT_ROOT / "02_audit_logging" / "storage" / "worm"
SOT_VALIDATOR = PROJECT_ROOT / "12_tooling" / "cli" / "sot_validator.py"
STABILITY_GATE = PROJECT_ROOT / "12_tooling" / "cli" / "stability_gate.py"

DEFAULT_WORKSPACE_ROOT = Path(
    os.environ.get(
        "SSID_WORKSPACE_ROOT",
        os.path.join(os.path.expanduser("~"), ".ssid", "worktrees"),
    )
)

# ---------------------------------------------------------------------------
# Exit code constants
# ---------------------------------------------------------------------------

EXIT_SUCCESS = 0
EXIT_GATE_FAILURE = 1
EXIT_SPEC_INVALID = 2
EXIT_TOOLING_ERROR = 3

# ---------------------------------------------------------------------------
# Spec validation constants
# ---------------------------------------------------------------------------

REQUIRED_SPEC_KEYS = [
    "task_id",
    "title",
    "task_type",
    "scope_allowlist",
    "forbidden_paths",
    "required_checks",
    "acceptance_criteria",
    "evidence_outputs",
]

VALID_TASK_TYPES = ["bootstrap", "tooling", "tests", "docs"]

ALWAYS_FORBIDDEN = ["./", "/mnt/data", "**/.git/**", "**/secrets/**"]

# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def _utc_now() -> str:
    """Return the current UTC timestamp in compact ISO-8601 format."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _sha256_file(path: Path) -> str:
    """Compute the SHA-256 hex digest of a file, reading in 8 KiB chunks."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_bytes(data: bytes) -> str:
    """Compute the SHA-256 hex digest of an in-memory byte string."""
    return hashlib.sha256(data).hexdigest()


def _run_cmd(cmd: list[str], label: str) -> tuple[int, str, str]:
    """Run a subprocess at PROJECT_ROOT and return (returncode, stdout, stderr).

    Args:
        cmd: Command and arguments to execute.
        label: Human-readable label used for logging context.
    """
    proc = subprocess.run(
        cmd,
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout, proc.stderr


# ---------------------------------------------------------------------------
# Spec validation helpers
# ---------------------------------------------------------------------------


def _validate_spec_structure(spec: object) -> str | None:
    """Check that *spec* is a dict with all required top-level keys.

    Returns an error message string on failure, or ``None`` on success.
    """
    if not isinstance(spec, dict):
        return "Spec must be a YAML mapping"

    missing = [k for k in REQUIRED_SPEC_KEYS if k not in spec]
    if missing:
        return f"Missing required keys: {missing}"

    return None


def _validate_task_type(spec: dict) -> str | None:
    """Validate that ``task_type`` is one of the allowed values.

    Returns an error message on failure, or ``None`` on success.
    """
    if spec.get("task_type") not in VALID_TASK_TYPES:
        return (
            f"Invalid task_type '{spec.get('task_type')}'. "
            f"Must be one of {VALID_TASK_TYPES}"
        )
    return None


def _validate_scope_allowlist(spec: dict) -> str | None:
    """Validate the ``scope_allowlist`` field.

    Ensures the list is non-empty and does not grant root-level write access.
    Returns an error message on failure, or ``None`` on success.
    """
    allowlist = spec.get("scope_allowlist", [])
    if not isinstance(allowlist, list) or not allowlist:
        return "scope_allowlist must be a non-empty list"

    for p in allowlist:
        if p in ("./", "/", "."):
            return f"scope_allowlist contains root write '{p}' (forbidden)"

    return None


def _validate_forbidden_paths(spec: dict) -> str | None:
    """Validate the ``forbidden_paths`` field.

    Ensures the field is a list and contains every entry from
    :data:`ALWAYS_FORBIDDEN`.  Returns an error message on failure, or
    ``None`` on success.
    """
    forbidden = spec.get("forbidden_paths", [])
    if not isinstance(forbidden, list):
        return "forbidden_paths must be a list"

    for fp in ALWAYS_FORBIDDEN:
        if fp not in forbidden:
            return f"forbidden_paths must include '{fp}'"

    return None


# ---------------------------------------------------------------------------
# verify-spec
# ---------------------------------------------------------------------------


def verify_spec(spec_path: str) -> int:
    """Validate a TaskSpec YAML file against the required schema.

    Checks file existence, YAML parse-ability, required keys, task_type,
    scope_allowlist safety, and forbidden_paths completeness.

    Returns:
        EXIT_SUCCESS on success (PASS), EXIT_GATE_FAILURE on any validation
        failure.
    """
    path = Path(spec_path)
    if not path.exists():
        print(f"FAIL: Spec file not found: {spec_path}")
        return EXIT_GATE_FAILURE

    try:
        with open(path, "r", encoding="utf-8") as f:
            spec = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        print(f"FAIL: Invalid YAML: {exc}")
        return EXIT_GATE_FAILURE

    # Run each validator; short-circuit on first failure
    for validator in (
        _validate_spec_structure,
        _validate_task_type,
        _validate_scope_allowlist,
        _validate_forbidden_paths,
    ):
        err = validator(spec)
        if err is not None:
            print(f"FAIL: {err}")
            return EXIT_GATE_FAILURE

    print(f"PASS: Spec '{spec.get('task_id')}' validated successfully")
    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------


def init_dirs() -> int:
    """Ensure that the required audit directories exist.

    Creates ``02_audit_logging/agent_runs/`` and ``02_audit_logging/reports/``
    if they do not already exist.

    Returns:
        Always EXIT_SUCCESS (PASS).
    """
    AGENT_RUNS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"PASS: Audit directories ensured: {AGENT_RUNS_DIR.relative_to(PROJECT_ROOT)}, {REPORTS_DIR.relative_to(PROJECT_ROOT)}")
    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# start
# ---------------------------------------------------------------------------


def _check_git_clean() -> str | None:
    """Verify the working tree has no uncommitted changes.

    Returns an error message if git status is dirty or fails, ``None``
    otherwise.
    """
    rc, stdout, stderr = _run_cmd(["git", "status", "--porcelain"], "git status")
    if rc != 0:
        return f"git status failed: {stderr.strip()}"
    if stdout.strip():
        return "Git status not clean. Commit or stash changes first."
    return None


def _check_not_on_main() -> tuple[str | None, str]:
    """Verify the current branch is not main/master.

    Returns:
        A tuple of (error_message_or_None, branch_name).
    """
    rc, stdout, _ = _run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], "git branch")
    branch = stdout.strip()
    if branch in ("main", "master"):
        return f"Cannot start task on branch '{branch}'. Create a feature branch first.", branch
    return None, branch


def _create_run_manifest(
    run_dir: Path, task_id: str, branch: str, spec_path: Path,
) -> None:
    """Create the initial run manifest and copy the spec into the run dir.

    Writes ``taskspec.yaml``, ``run_manifest.json``, and an empty
    ``commands.log`` to *run_dir*.
    """
    shutil.copy2(str(spec_path), str(run_dir / "taskspec.yaml"))

    manifest = {
        "task_id": task_id,
        "branch": branch,
        "started_utc": _utc_now(),
        "status": "in_progress",
        "spec_sha256": _sha256_file(spec_path),
    }
    manifest_path = run_dir / "run_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    (run_dir / "commands.log").write_text("", encoding="utf-8")


def start_task(task_id: str, spec_path: str) -> int:
    """Initialize an agent run for the given task.

    Validates the spec, checks git cleanliness, ensures we are not on the
    main branch, then creates the run directory with initial artifacts.

    Returns:
        EXIT_SUCCESS on success (PASS), EXIT_GATE_FAILURE on any failure.
    """
    path = Path(spec_path)
    if not path.exists():
        print(f"FAIL: Spec file not found: {spec_path}")
        return EXIT_GATE_FAILURE

    # Verify spec first
    if verify_spec(spec_path) != EXIT_SUCCESS:
        return EXIT_GATE_FAILURE

    # Check git status clean
    err = _check_git_clean()
    if err is not None:
        print(f"FAIL: {err}")
        return EXIT_GATE_FAILURE

    # Check not on main
    err, branch = _check_not_on_main()
    if err is not None:
        print(f"FAIL: {err}")
        return EXIT_GATE_FAILURE

    # Create agent run directory and initial artifacts
    run_dir = AGENT_RUNS_DIR / task_id
    run_dir.mkdir(parents=True, exist_ok=True)
    _create_run_manifest(run_dir, task_id, branch, path)

    print(f"PASS: Agent run initialized at {run_dir.relative_to(PROJECT_ROOT)}")
    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# finalize - helpers
# ---------------------------------------------------------------------------


def _generate_patch_diff(run_dir: Path) -> str:
    """Generate a patch diff of uncommitted changes and write it to *run_dir*.

    Returns:
        The raw diff output as a string.
    """
    rc, stdout, _ = _run_cmd(["git", "diff", "HEAD"], "git diff")
    patch_path = run_dir / "patch.diff"
    patch_path.write_text(stdout, encoding="utf-8")
    return stdout


def _collect_changed_file_hashes(run_dir: Path) -> list[str]:
    """Identify changed files and write their SHA-256 hashes to *run_dir*.

    Creates ``file_hashes.json`` in *run_dir* and returns the list of
    changed file paths (relative to PROJECT_ROOT).
    """
    rc, stdout, _ = _run_cmd(["git", "diff", "--name-only", "HEAD"], "git diff names")
    changed_files = [f for f in stdout.strip().splitlines() if f]
    file_hashes = {}
    for fname in changed_files:
        fpath = PROJECT_ROOT / fname
        if fpath.exists():
            file_hashes[fname] = _sha256_file(fpath)
    hashes_path = run_dir / "file_hashes.json"
    hashes_path.write_text(
        json.dumps(file_hashes, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return changed_files


def _run_single_check(
    tool_path: Path | None,
    tool_args: list[str],
    check_name: str,
) -> dict:
    """Execute a single check tool and return a result dict.

    Args:
        tool_path: Path to the tool script, or ``None`` to run *tool_args*
            directly (e.g. for ``pytest``).
        tool_args: Full command list to execute.
        check_name: Human-readable name for the check.

    Returns:
        A dict with keys ``check``, ``exit_code``, ``result``, and
        optionally ``detail``.
    """
    if tool_path is not None and not tool_path.exists():
        print(f"FAIL: {check_name}.py not found")
        return {"check": check_name, "result": "FAIL", "detail": "not found"}

    rc, stdout, stderr = _run_cmd(tool_args, check_name)
    result = "PASS" if rc == 0 else "FAIL"
    if rc != 0:
        print(f"FAIL: {check_name} (exit={rc})")
    return {"check": check_name, "exit_code": rc, "result": result}


def _run_required_checks() -> tuple[list[dict], bool]:
    """Run all required checks (stability_gate, sot_validator, pytest).

    Returns:
        A tuple of (list_of_check_results, overall_pass).
    """
    checks_results: list[dict] = []
    overall_pass = True

    # 1. stability_gate
    result = _run_single_check(
        STABILITY_GATE,
        [sys.executable, str(STABILITY_GATE), "--run"],
        "stability_gate",
    )
    checks_results.append(result)
    if result["result"] != "PASS":
        overall_pass = False

    # 2. sot_validator
    result = _run_single_check(
        SOT_VALIDATOR,
        [sys.executable, str(SOT_VALIDATOR), "--verify-all"],
        "sot_validator",
    )
    checks_results.append(result)
    if result["result"] != "PASS":
        overall_pass = False

    # 3. pytest (no tool_path check needed - always available)
    result = _run_single_check(
        None,
        [sys.executable, "-m", "pytest", "-q"],
        "pytest",
    )
    checks_results.append(result)
    if result["result"] != "PASS":
        overall_pass = False

    return checks_results, overall_pass


def _create_worm_zip(run_dir: Path, utc_stamp: str) -> tuple[Path, str, int]:
    """Package all run artifacts into a WORM-compliant ZIP archive.

    Args:
        run_dir: The agent run directory whose contents to archive.
        utc_stamp: UTC timestamp string used for the WORM subdirectory.

    Returns:
        A tuple of (zip_path, zip_sha256, zip_size_bytes).
    """
    worm_dir = WORM_BASE / "BOOTSTRAP" / utc_stamp
    worm_dir.mkdir(parents=True, exist_ok=True)
    zip_name = "bootstrap_pr_0001_acceptance.zip"
    zip_path = worm_dir / zip_name

    with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED) as zf:
        for item in sorted(run_dir.rglob("*")):
            if item.is_file():
                arcname = str(item.relative_to(run_dir))
                zf.write(str(item), arcname)

    zip_sha256 = _sha256_file(zip_path)
    zip_size = zip_path.stat().st_size
    return zip_path, zip_sha256, zip_size


def _build_and_write_evidence(
    run_dir: Path,
    task_id: str,
    utc_stamp: str,
    overall_pass: bool,
    checks_results: list[dict],
    changed_files: list[str],
    zip_path: Path,
    zip_sha256: str,
    zip_size: int,
) -> Path:
    """Build the evidence payload and write it to ``evidence.json``.

    Returns:
        The path to the written ``evidence.json`` file.
    """
    evidence = {
        "task_id": task_id,
        "finalized_utc": utc_stamp,
        "overall": "PASS" if overall_pass else "FAIL",
        "checks": checks_results,
        "changed_files": sorted(changed_files),
        "worm_zip": {
            "path": str(zip_path.relative_to(PROJECT_ROOT)) if zip_path.is_relative_to(PROJECT_ROOT) else str(zip_path),
            "sha256": zip_sha256,
            "size_bytes": zip_size,
        },
    }
    evidence_path = run_dir / "evidence.json"
    evidence_path.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return evidence_path


def _update_run_manifest(
    run_dir: Path,
    task_id: str,
    utc_stamp: str,
    overall_pass: bool,
    evidence_path: Path,
) -> None:
    """Update (or create) the run manifest with finalization metadata.

    Sets ``finalized_utc``, ``status``, and ``evidence_sha256``.
    """
    manifest_path = run_dir / "run_manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        manifest = {"task_id": task_id}
    manifest["finalized_utc"] = utc_stamp
    manifest["status"] = "completed" if overall_pass else "failed"
    manifest["evidence_sha256"] = _sha256_file(evidence_path)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# finalize - main entry point
# ---------------------------------------------------------------------------


def finalize_task(task_id: str) -> int:
    """Finalize an agent run: run checks, produce evidence, create WORM ZIP.

    Orchestrates the full finalization pipeline:
    1. Generate patch diff and file hashes
    2. Run required checks (stability_gate, sot_validator, pytest)
    3. Create WORM ZIP archive
    4. Build and write evidence.json
    5. Update the run manifest with final status

    Returns:
        EXIT_SUCCESS if all checks passed (PASS), EXIT_GATE_FAILURE
        otherwise (FAIL).
    """
    run_dir = AGENT_RUNS_DIR / task_id
    if not run_dir.exists():
        print(f"FAIL: Agent run directory not found: {run_dir}")
        return EXIT_GATE_FAILURE

    utc_stamp = _utc_now()

    # Step 1: Capture diff and file hashes
    _generate_patch_diff(run_dir)
    changed_files = _collect_changed_file_hashes(run_dir)

    # Step 2: Run required checks
    checks_results, overall_pass = _run_required_checks()

    # Step 3: Create WORM ZIP
    zip_path, zip_sha256, zip_size = _create_worm_zip(run_dir, utc_stamp)

    # Step 4: Build evidence
    evidence_path = _build_and_write_evidence(
        run_dir, task_id, utc_stamp, overall_pass,
        checks_results, changed_files,
        zip_path, zip_sha256, zip_size,
    )

    # Step 5: Update manifest
    _update_run_manifest(run_dir, task_id, utc_stamp, overall_pass, evidence_path)

    # Report results
    status = "PASS" if overall_pass else "FAIL"
    print(f"\nFINALIZE: {status}")
    print(f"Evidence: {evidence_path.relative_to(PROJECT_ROOT)}")
    print(f"WORM ZIP: {zip_path.relative_to(PROJECT_ROOT)}")
    print(f"ZIP SHA256: {zip_sha256}")
    print(f"ZIP Size: {zip_size} bytes")

    return EXIT_SUCCESS if overall_pass else EXIT_GATE_FAILURE


# ---------------------------------------------------------------------------
# smoke-e2e
# ---------------------------------------------------------------------------


_SMOKE_SPEC = {
    "task_id": "SMOKE_E2E_TEST",
    "title": "Smoke E2E lifecycle test",
    "task_type": "tooling",
    "scope_allowlist": ["12_tooling/cli/"],
    "forbidden_paths": ["./", "/mnt/data", "**/.git/**", "**/secrets/**"],
    "required_checks": ["python -m pytest -q"],
    "acceptance_criteria": ["Smoke test passes"],
    "evidence_outputs": [
        "02_audit_logging/agent_runs/SMOKE_E2E_TEST/evidence.json",
    ],
}


def _smoke_verify_artifact(path: Path, label: str) -> str | None:
    """Check that an artifact file exists and is non-empty.

    Returns an error message on failure, or ``None`` on success.
    """
    if not path.exists():
        return f"Missing artifact: {label} ({path.name})"
    if path.stat().st_size == 0:
        return f"Empty artifact: {label} ({path.name})"
    return None


def _smoke_verify_json(path: Path, label: str) -> str | None:
    """Check that a JSON artifact is valid and deterministic.

    Verifies the file is parseable JSON and that re-serializing with
    ``sort_keys=True`` produces identical output (determinism check).

    Returns an error message on failure, or ``None`` on success.
    """
    err = _smoke_verify_artifact(path, label)
    if err is not None:
        return err

    raw = path.read_text(encoding="utf-8")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        return f"Invalid JSON in {label}: {exc}"

    # Determinism: re-serialize and compare
    reserialized = json.dumps(parsed, indent=2, sort_keys=True) + "\n"
    if raw != reserialized:
        return f"Non-deterministic JSON in {label}: re-serialization differs"

    return None


def _smoke_verify_zip(path: Path, label: str, expected: list[str]) -> str | None:
    """Check that a ZIP archive exists and contains the expected entries.

    Args:
        path: Path to the ZIP file.
        label: Human-readable label for error messages.
        expected: List of archive entry names that must be present.

    Returns an error message on failure, or ``None`` on success.
    """
    err = _smoke_verify_artifact(path, label)
    if err is not None:
        return err

    try:
        with zipfile.ZipFile(str(path), "r") as zf:
            names = set(zf.namelist())
    except zipfile.BadZipFile as exc:
        return f"Corrupt ZIP {label}: {exc}"

    missing = [e for e in expected if e not in names]
    if missing:
        return f"ZIP {label} missing entries: {missing}"

    return None


def smoke_e2e() -> int:
    """Run the full start -> edit -> finalize lifecycle as a smoke test.

    Uses a self-contained task ID (``SMOKE_E2E_TEST``) with a synthetic
    spec.  Does NOT run external gate checks -- instead uses synthetic
    PASS results to verify the artifact-generation pipeline only.

    Steps:
        1. Write a synthetic TaskSpec YAML to a temp file
        2. Create the agent-run directory with start artifacts
        3. Perform a dummy edit (write a marker file)
        4. Finalize: generate patch.diff, evidence.json, WORM ZIP
        5. Verify all artifacts exist, have valid format, and ZIP
           contains the expected entries
        6. Clean up the smoke-test run directory

    Returns:
        EXIT_SUCCESS (0) if all artifacts are present and valid,
        EXIT_GATE_FAILURE (1) if any verification fails.
    """
    task_id = "SMOKE_E2E_TEST"
    utc_stamp = _utc_now()
    errors: list[str] = []

    print(f"SMOKE-E2E: Starting lifecycle test ({task_id})")

    # -- Step 1: Write synthetic spec to a temp file --------------------------
    tmp_dir = Path(tempfile.mkdtemp(prefix="smoke_e2e_"))
    spec_path = tmp_dir / "smoke_spec.yaml"
    spec_path.write_text(
        yaml.dump(_SMOKE_SPEC, sort_keys=True), encoding="utf-8",
    )

    # Validate the synthetic spec itself
    if verify_spec(str(spec_path)) != EXIT_SUCCESS:
        print("FAIL: Synthetic spec failed validation (internal error)")
        shutil.rmtree(str(tmp_dir), ignore_errors=True)
        return EXIT_GATE_FAILURE

    # -- Step 2: Create agent-run directory (start phase) ---------------------
    run_dir = AGENT_RUNS_DIR / task_id
    run_dir.mkdir(parents=True, exist_ok=True)
    _create_run_manifest(run_dir, task_id, "smoke-e2e", spec_path)

    print(f"SMOKE-E2E: Start phase complete -> {run_dir.relative_to(PROJECT_ROOT)}")

    # Verify start artifacts (commands.log starts empty, so only check existence)
    for artifact, label in [
        (run_dir / "taskspec.yaml", "taskspec"),
        (run_dir / "run_manifest.json", "run_manifest"),
    ]:
        err = _smoke_verify_artifact(artifact, label)
        if err is not None:
            errors.append(f"[start] {err}")
    if not (run_dir / "commands.log").exists():
        errors.append("[start] Missing artifact: commands_log (commands.log)")

    # -- Step 3: Dummy edit ---------------------------------------------------
    marker_path = run_dir / "smoke_marker.txt"
    marker_path.write_text(
        f"SMOKE_E2E dummy edit marker\ntimestamp: {utc_stamp}\n",
        encoding="utf-8",
    )
    # Append to commands.log to simulate an edit action
    with open(run_dir / "commands.log", "a", encoding="utf-8") as log:
        log.write(f"[{utc_stamp}] smoke_e2e: wrote marker file\n")

    print("SMOKE-E2E: Edit phase complete -> smoke_marker.txt written")

    # -- Step 4: Finalize (self-contained, no external checks) ----------------
    # Generate patch.diff (will capture actual git diff, which is fine)
    _generate_patch_diff(run_dir)

    # Collect file hashes
    changed_files = _collect_changed_file_hashes(run_dir)

    # Synthetic check results (we skip actual gates for the smoke test)
    checks_results = [
        {"check": "smoke_e2e_synthetic", "exit_code": 0, "result": "PASS"},
    ]
    overall_pass = True

    # Create WORM ZIP
    worm_dir = WORM_BASE / "SMOKE_E2E" / utc_stamp
    worm_dir.mkdir(parents=True, exist_ok=True)
    zip_name = "smoke_e2e_evidence.zip"
    zip_path = worm_dir / zip_name

    with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED) as zf:
        for item in sorted(run_dir.rglob("*")):
            if item.is_file():
                arcname = str(item.relative_to(run_dir))
                zf.write(str(item), arcname)

    zip_sha256 = _sha256_file(zip_path)
    zip_size = zip_path.stat().st_size

    # Build evidence.json
    evidence_path = _build_and_write_evidence(
        run_dir, task_id, utc_stamp, overall_pass,
        checks_results, changed_files,
        zip_path, zip_sha256, zip_size,
    )

    # Update manifest
    _update_run_manifest(run_dir, task_id, utc_stamp, overall_pass, evidence_path)

    print("SMOKE-E2E: Finalize phase complete")

    # -- Step 5: Verify all artifacts -----------------------------------------

    # patch.diff (may be empty if no git changes, but file must exist)
    if not (run_dir / "patch.diff").exists():
        errors.append("[finalize] Missing artifact: patch_diff (patch.diff)")

    # evidence.json (must be valid, deterministic JSON)
    err = _smoke_verify_json(evidence_path, "evidence_json")
    if err is not None:
        errors.append(f"[finalize] {err}")
    else:
        # Additional evidence structure checks
        evidence_data = json.loads(evidence_path.read_text(encoding="utf-8"))
        for key in ("task_id", "finalized_utc", "overall", "checks", "worm_zip"):
            if key not in evidence_data:
                errors.append(f"[finalize] evidence.json missing key: {key}")

    # run_manifest.json (must be valid, deterministic JSON with final status)
    err = _smoke_verify_json(run_dir / "run_manifest.json", "run_manifest_final")
    if err is not None:
        errors.append(f"[finalize] {err}")
    else:
        manifest_data = json.loads(
            (run_dir / "run_manifest.json").read_text(encoding="utf-8")
        )
        if manifest_data.get("status") != "completed":
            errors.append(
                f"[finalize] run_manifest status={manifest_data.get('status')!r}, "
                f"expected 'completed'"
            )

    # file_hashes.json (may contain empty dict if no tracked files changed)
    fh_path = run_dir / "file_hashes.json"
    if not fh_path.exists():
        errors.append("[finalize] Missing artifact: file_hashes (file_hashes.json)")
    else:
        err = _smoke_verify_json(fh_path, "file_hashes")
        if err is not None:
            errors.append(f"[finalize] {err}")

    # ZIP (must contain key artifacts)
    expected_zip_entries = [
        "taskspec.yaml",
        "run_manifest.json",
        "commands.log",
        "smoke_marker.txt",
        "patch.diff",
    ]
    err = _smoke_verify_zip(zip_path, "worm_zip", expected_zip_entries)
    if err is not None:
        errors.append(f"[finalize] {err}")

    # -- Step 6: Cleanup and report -------------------------------------------
    shutil.rmtree(str(tmp_dir), ignore_errors=True)
    shutil.rmtree(str(run_dir), ignore_errors=True)
    shutil.rmtree(str(worm_dir), ignore_errors=True)
    # Clean up empty parent dirs if possible
    for d in (WORM_BASE / "SMOKE_E2E",):
        try:
            d.rmdir()
        except OSError:
            pass

    if errors:
        print("\nSMOKE-E2E: FAIL")
        for e in errors:
            print(f"  - {e}")
        return EXIT_GATE_FAILURE

    print("\nSMOKE-E2E: PASS")
    print("  - Start artifacts: taskspec.yaml, run_manifest.json, commands.log")
    print("  - Edit artifacts: smoke_marker.txt, commands.log updated")
    print("  - Finalize artifacts: patch.diff, evidence.json, file_hashes.json")
    print("  - WORM ZIP: contains all expected entries")
    print("  - Determinism: all JSON outputs verified sort_keys round-trip")
    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """Parse CLI arguments and dispatch to the appropriate subcommand.

    Exit codes:
        EXIT_SUCCESS (0) -- command completed successfully
        EXIT_GATE_FAILURE (1) -- a gate check or validation failed
        EXIT_SPEC_INVALID (2) -- spec file missing or invalid
        EXIT_TOOLING_ERROR (3) -- CLI usage error (missing arguments)
    """
    parser = argparse.ArgumentParser(
        prog="automation_loop.py",
        description="Deterministic TaskSpec-driven run framework.",
    )
    parser.add_argument("--verify-spec", action="store_true", help="Validate a TaskSpec YAML")
    parser.add_argument("--init", action="store_true", help="Initialize audit directories")
    parser.add_argument("--start", action="store_true", help="Start an agent run")
    parser.add_argument("--finalize", action="store_true", help="Finalize an agent run")
    parser.add_argument("--smoke-e2e", action="store_true", help="Run full lifecycle smoke test")
    parser.add_argument("--spec", type=str, help="Path to TaskSpec YAML")
    parser.add_argument("--task", type=str, help="Task ID")
    args = parser.parse_args()

    if args.verify_spec:
        if not args.spec:
            print("FAIL: --verify-spec requires --spec <path>")
            return EXIT_TOOLING_ERROR
        return verify_spec(args.spec)

    if args.init:
        return init_dirs()

    if args.start:
        if not args.task or not args.spec:
            print("FAIL: --start requires --task <ID> and --spec <path>")
            return EXIT_TOOLING_ERROR
        return start_task(args.task, args.spec)

    if args.finalize:
        if not args.task:
            print("FAIL: --finalize requires --task <ID>")
            return EXIT_TOOLING_ERROR
        return finalize_task(args.task)

    if args.smoke_e2e:
        return smoke_e2e()

    parser.print_help()
    return EXIT_TOOLING_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
