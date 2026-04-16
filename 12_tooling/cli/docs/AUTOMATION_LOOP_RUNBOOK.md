# Automation Loop Runbook

## Overview

`automation_loop.py` is the deterministic TaskSpec-driven run framework.
It enforces scoped, auditable, PR-only agent work. Every agent task follows
the same lifecycle: verify, start, implement, finalize, push, PR.

This runbook covers:

1. [Pre-flight Checklist](#pre-flight-checklist) -- verify before every task
2. [1-Command-Per-Task Reference](#1-command-per-task-reference) -- copy-paste commands
3. [Typical Workflow](#typical-workflow) -- end-to-end steps
4. [Workspace Paths](#workspace-paths) -- standard paths for all environments
5. [Troubleshooting: General](#troubleshooting-general) -- common errors
6. [Troubleshooting: Windows](#troubleshooting-windows) -- Windows-specific issues
7. [Troubleshooting: WSL](#troubleshooting-wsl) -- WSL-specific issues
8. [Troubleshooting: Codespaces](#troubleshooting-codespaces) -- Codespaces-specific issues

---

## Pre-flight Checklist

Run through this checklist before starting **any** agent task.

- [ ] **Feature branch**: You are NOT on `main`.
  ```bash
  git branch --show-current   # must NOT print "main"
  ```
- [ ] **Clean working tree**: No uncommitted changes.
  ```bash
  git status --short           # must produce no output
  ```
- [ ] **Up-to-date with main**: Your branch includes latest upstream.
  ```bash
  git fetch origin && git log --oneline origin/main..HEAD
  ```
- [ ] **Python 3.11+** is available:
  ```bash
  python --version             # must be 3.11 or higher
  ```
- [ ] **PyYAML installed**:
  ```bash
  python -c "import yaml; print(yaml.__version__)"
  ```
- [ ] **TaskSpec exists and is valid**: `--verify-spec` passes.
  ```bash
  python 12_tooling/cli/automation_loop.py --verify-spec --spec <path-to-spec>
  ```
- [ ] **Scope check**: The `scope_allowlist` in your TaskSpec covers all paths you intend to modify.
- [ ] **Forbidden check**: The `forbidden_paths` in your TaskSpec does NOT include paths you need.
- [ ] **Audit directories exist**: `--init` has been run at least once.
  ```bash
  python 12_tooling/cli/automation_loop.py --init
  ```
- [ ] **Workspace root set** (optional but recommended):
  ```bash
  echo $SSID_WORKSPACE_ROOT   # should point to your worktree root
  ```

---

## 1-Command-Per-Task Reference

Copy-paste these commands directly. Replace `<TASK_ID>` with your task
identifier (e.g., `PH2_LOOP_DOC_001`) and `<SPEC_PATH>` with the full
path to the TaskSpec YAML.

### Verify a spec

```bash
python 12_tooling/cli/automation_loop.py --verify-spec --spec <SPEC_PATH>
```

Validates YAML schema: required keys, allowlist/forbidden paths, no root writes.

**What it checks:**
- All required fields are present (`task_id`, `title`, `scope_allowlist`, etc.)
- `scope_allowlist` paths exist or are valid targets
- `forbidden_paths` do not overlap with `scope_allowlist`
- No root-level write paths are declared

### Initialize audit directories (first-time only)

```bash
python 12_tooling/cli/automation_loop.py --init
```

Ensures `02_audit_logging/agent_runs/` and `02_audit_logging/reports/` exist.
Creates no root-level files. Safe to run multiple times.

### Start a task

```bash
python 12_tooling/cli/automation_loop.py --start --task <TASK_ID> --spec <SPEC_PATH>
```

- Verifies git status is clean and branch is not main.
- Creates `02_audit_logging/agent_runs/<TASK_ID>/` with initial manifest.

### Finalize a task

```bash
python 12_tooling/cli/automation_loop.py --finalize --task <TASK_ID>
```

- Generates `patch.diff`, `file_hashes.json`, `evidence.json`.
- Runs required checks (stability_gate, sot_validator, pytest).
- Creates WORM ZIP under `02_audit_logging/storage/worm/BOOTSTRAP/<UTC>/`.

### Run all gates

```bash
python 12_tooling/cli/run_all_gates.py
```

Runs the full gate sequence (structure guard, SoT validator, duplicate guard,
repo separation guard, pytest) and reports PASS/FAIL per gate.

### Run stability gate only

```bash
python 12_tooling/cli/stability_gate.py --run
```

Runs the stop-on-first-failure gate sequence: ROOT-24-LOCK, git-clean,
SoT verify, pytest, evidence write test. See `STABILITY_GATE_RUNBOOK.md`
for full details.

### Run SoT validator only

```bash
python 12_tooling/cli/sot_validator.py --verify-all
```

Verifies source-of-truth hashes and cross-references are consistent.

---

## Typical Workflow

```
1. git fetch origin && git checkout -b task/<TASK_ID> origin/main
2. python 12_tooling/cli/automation_loop.py --verify-spec --spec <SPEC_PATH>
3. python 12_tooling/cli/automation_loop.py --init
4. python 12_tooling/cli/automation_loop.py --start --task <TASK_ID> --spec <SPEC_PATH>
5. ... implement changes within scope_allowlist ...
6. git add <files> && git commit -m "<message>"
7. python 12_tooling/cli/automation_loop.py --finalize --task <TASK_ID>
8. git push -u origin task/<TASK_ID>
9. gh pr create --title "<PR title>" --body "<PR body>"
```

**Important:** Always branch from `origin/main` (not local `main`) to avoid
picking up uncommitted or stale local changes.

---

## Workspace Paths

All agent workspaces, scratch files, and build artifacts use the
**SSID workspace root**. Do NOT use legacy or deprecated workspace paths.

### Standard paths by environment

| Environment | Workspace Root | Example Worktree |
|-------------|---------------|------------------|
| **Windows (native)** | `${HOME} | `${HOME} |
| **WSL / Linux** | `~/.ssid/worktrees/` | `~/.ssid/worktrees/PH2_LOOP_DOC_001` |
| **Codespaces** | `~/.ssid/worktrees/` | `~/.ssid/worktrees/PH2_LOOP_DOC_001` |

### Environment variable

Set `SSID_WORKSPACE_ROOT` to override the default location:

```bash
# Linux / WSL / Codespaces
export SSID_WORKSPACE_ROOT="$HOME/.ssid/worktrees"

# Windows (Git Bash)
export SSID_WORKSPACE_ROOT="/c/Users/$USER/.ssid/worktrees"

# Windows (PowerShell)
$env:SSID_WORKSPACE_ROOT = "$env:USERPROFILE\.ssid\worktrees"
```

### Rules

- All agent scratch files go under `$SSID_WORKSPACE_ROOT/<TASK_ID>/`.
- Build artifacts and temporary outputs go under `$SSID_WORKSPACE_ROOT/<TASK_ID>/`.
- Never write workspace artifacts to the repo root or to legacy paths.
- The worktree directory is per-task and disposable after the PR merges.

---

## Troubleshooting: General

| Symptom | Cause | Fix |
|---------|-------|-----|
| "Missing required key" | TaskSpec YAML incomplete | Add missing fields per the spec schema. Run `--verify-spec` to see which keys are absent. |
| "Branch is main" | Must work on feature branch | `git checkout -b task/<ID> origin/main`. Never run `--start` on main. |
| "Git status not clean" | Uncommitted changes | Commit or stash changes first: `git stash` or `git add <files> && git commit`. |
| "sot_validator not found" | Missing CLI tool | Verify `12_tooling/cli/sot_validator.py` exists. Re-pull main if missing. |
| "Forbidden path violation" | Agent modified a path in `forbidden_paths` | Undo the offending file change. Check your TaskSpec `scope_allowlist` covers the path, or update `forbidden_paths` if the restriction was too broad. |
| "Branch conflict" / merge failure | Feature branch diverged from main | Rebase: `git fetch origin && git rebase origin/main`. Resolve conflicts, then re-run `--finalize`. |
| "WORM creation failed" | Permission error or missing directory | Ensure `02_audit_logging/storage/worm/` exists and is writable. Run `--init` if directories were deleted. |
| "WORM ZIP already exists" | Duplicate finalize attempt | Each finalize creates a unique UTC-stamped directory. If the timestamp collides, wait one second and retry. |
| "Scope violation" | File modified outside `scope_allowlist` | Move the change to an allowed path, or update the TaskSpec to include the path (requires re-verification). |
| "Evidence hash mismatch" | Files changed between commit and finalize | Ensure no files were modified after the last commit. Run `git status` to confirm a clean tree. |
| Unexpected Python import error | Missing dependency | Install required packages: `pip install pyyaml`. The tooling requires Python 3.11+ and PyYAML. |
| Finalize passes but PR checks fail | Stability gate runs in CI with stricter env | Run `python 12_tooling/cli/stability_gate.py --run` locally before pushing to catch issues early. |
| "Expected 24 roots, found N" | ROOT-24-LOCK violated | Remove unauthorized root dirs/files. Only the 24 numbered directories (`01_ai_layer/` through `24_meta_orchestration/`) plus repo config files are allowed at root. |

---

## Troubleshooting: Windows

Issues specific to running the automation loop on Windows (native or Git Bash).

| Symptom | Cause | Fix |
|---------|-------|-----|
| `FileNotFoundError` with backslash paths | Python receiving mixed path separators | Use forward slashes in all CLI arguments: `12_tooling/cli/automation_loop.py`, not `12_tooling\cli\automation_loop.py`. Git Bash and Python both accept forward slashes on Windows. |
| pytest `basetemp` errors or permission denied on temp files | Default temp path too long or locked by antivirus | Use `--basetemp` to set a short temp path: `python -m pytest -q --basetemp=C:/tmp/pytest`. Avoid paths with spaces. |
| `python` not found but `python3` works (or vice versa) | Python launcher aliasing differs between Git Bash and cmd | In Git Bash, use `python` (the `py` launcher does not work). In PowerShell/cmd, use `python` or `py -3`. Verify with `python --version`. |
| Line ending warnings from git | CRLF/LF mismatch | Set `git config core.autocrlf true` on Windows. The repo `.gitattributes` should handle most cases. If diffs show every line changed, run `git diff --ignore-cr-at-eol`. |
| `UnicodeDecodeError` reading files | Non-UTF-8 locale or BOM issues | Ensure files are saved as UTF-8 without BOM. Set `PYTHONUTF8=1` environment variable: `set PYTHONUTF8=1` (cmd) or `$env:PYTHONUTF8=1` (PowerShell). |
| Git Bash vs PowerShell path differences | Git Bash uses `/c/Users/...`, PowerShell uses `${HOME} | Pick one shell and stay consistent. Git Bash is recommended for this project. If using PowerShell, translate paths: `${HOME} |
| Stability gate fails with "Permission denied" | Windows file locking (antivirus, editor) | Close editors/IDEs that may lock files in `02_audit_logging/`. Retry after a few seconds. Exclude the repo from real-time antivirus scanning if safe to do so. |
| `subprocess.CalledProcessError` on `--finalize` | A required check binary is not on PATH | Ensure `python` is on PATH in your current shell. For OPA checks, download the Windows binary and add its folder to PATH. |

---

## Troubleshooting: WSL

Issues specific to running under Windows Subsystem for Linux.

| Symptom | Cause | Fix |
|---------|-------|-----|
| `python3` works but `python` does not | Debian/Ubuntu default: `python3` only | Create a symlink: `sudo ln -s /usr/bin/python3 /usr/bin/python`, or install `python-is-python3` package: `sudo apt install python-is-python3`. |
| Wrong Python resolves (Windows Python from `/mnt/c/`) | WSL PATH includes Windows paths | Remove Windows Python from WSL PATH. Edit `~/.bashrc` and add: `export PATH=$(echo "$PATH" \| tr ':' '\n' \| grep -v /mnt/c/ \| tr '\n' ':')` or configure `/etc/wsl.conf` with `[interop] appendWindowsPath=false`. |
| Git shows all files as modified (chmod changes) | WSL mounts NTFS without Unix permissions | Set `git config core.fileMode false` in the repo. Alternatively, clone the repo inside the WSL filesystem (`~/projects/SSID`) instead of `/mnt/c/`. |
| Line endings differ between WSL and Windows | CRLF injected by Windows tools | Set `git config core.autocrlf input` inside WSL. This converts CRLF to LF on commit but does not alter checkout. |
| Slow I/O on `/mnt/c/` paths | NTFS access through WSL is slow | Clone the repo into the native WSL filesystem (`~/.ssid/worktrees/` or `~/projects/`). File operations are 5-10x faster on ext4. |
| `git config user.name` is wrong | WSL and Windows have separate git configs | Set git config inside WSL: `git config user.name "<your-name>"` and `git config user.email "<your-email>"` in the repo. |
| `gh` CLI not found | GitHub CLI not installed in WSL | Install: `sudo apt install gh` or follow the GitHub CLI install guide at https://cli.github.com/. Then authenticate: `gh auth login`. |

---

## Troubleshooting: Codespaces

Issues specific to running in GitHub Codespaces containers.

| Symptom | Cause | Fix |
|---------|-------|-----|
| Container paths differ from local | Codespace mounts repo at `/workspaces/<repo>` | Use relative paths from the repo root (e.g., `12_tooling/cli/automation_loop.py`) or set `SSID_WORKSPACE_ROOT` to `/workspaces/SSID/.ssid/worktrees`. |
| `pip install` fails with permission error | System Python is read-only in the container | Use `pip install --user pyyaml` or create a virtualenv: `python -m venv .venv && source .venv/bin/activate && pip install pyyaml`. |
| Network access blocked for `pip install` | Codespace network policy or proxy | Check if the devcontainer has `forwardPorts` configured. Use `pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org pyyaml` if behind a proxy. |
| Git identity not set | Codespace does not inherit local git config | Set in the codespace: `git config user.name "<your-name>"` and `git config user.email "<your-email>"`. Or configure `devcontainer.json` to set these automatically. |
| Evidence directory permission denied | Container user does not own audit directories | Run `sudo chown -R $(whoami) 02_audit_logging/` once after first clone. |
| OPA binary not available | OPA not pre-installed in the container | Download the Linux binary from the OPA releases page and place it on PATH. Or add to `devcontainer.json` features. |
| Port forwarding needed for local testing | Codespace does not auto-expose ports | Add ports to `.devcontainer/devcontainer.json` under `forwardPorts`, or use the Codespaces Ports panel to forward manually. |
| Prebuild cache stale | Codespace was created from an old prebuild | Rebuild the container via Command Palette > "Codespaces: Rebuild Container". Or delete and recreate the codespace. |

---

## Appendix: Command Quick Reference Card

All commands assume you are in the repo root directory.

```bash
# ---------- Setup ----------
git fetch origin && git checkout -b task/<TASK_ID> origin/main
python 12_tooling/cli/automation_loop.py --init

# ---------- Verify ----------
python 12_tooling/cli/automation_loop.py --verify-spec --spec 24_meta_orchestration/tasks/specs/<TASK_ID>.yaml

# ---------- Start ----------
python 12_tooling/cli/automation_loop.py --start --task <TASK_ID> --spec 24_meta_orchestration/tasks/specs/<TASK_ID>.yaml

# ---------- Implement ----------
# ... make your changes within scope_allowlist ...

# ---------- Validate ----------
python 12_tooling/cli/stability_gate.py --run
python 12_tooling/cli/run_all_gates.py
python 12_tooling/cli/sot_validator.py --verify-all
python -m pytest -q

# ---------- Finalize ----------
git add <files> && git commit -m "<message>"
python 12_tooling/cli/automation_loop.py --finalize --task <TASK_ID>

# ---------- Ship ----------
git push -u origin task/<TASK_ID>
gh pr create --title "<title>" --body "<body>"
```
