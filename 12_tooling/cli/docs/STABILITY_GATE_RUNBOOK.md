# Stability Gate Runbook

## Overview

`stability_gate.py` is the objective "ready" check for PR branches.
Runs a fixed sequence of gates; stops on first failure. Every PR must
pass all gates before merge.

This runbook covers:

1. [Quick Reference](#quick-reference) -- 1-command examples
2. [Gate Sequence](#gate-sequence) -- what runs and in what order
3. [CI vs Local](#ci-vs-local) -- differences between environments
4. [Workspace Paths](#workspace-paths) -- where evidence and artifacts go
5. [Troubleshooting: General](#troubleshooting-general) -- common errors
6. [Troubleshooting: Windows](#troubleshooting-windows) -- Windows-specific issues
7. [Troubleshooting: WSL](#troubleshooting-wsl) -- WSL-specific issues
8. [Troubleshooting: Codespaces](#troubleshooting-codespaces) -- Codespaces-specific issues

---

## Quick Reference

One-command examples for common operations:

```bash
# Run all stability gates (standard usage)
python 12_tooling/cli/stability_gate.py --run

# Run pytest independently to debug test failures
python -m pytest -q 12_tooling/

# Check ROOT-24-LOCK manually (count root directories)
ls -d [0-9][0-9]_*/ | wc -l   # must output 24

# Verify SoT independently
python 12_tooling/cli/sot_validator.py --verify-all

# Check git status is clean
git status --short   # must produce no output

# Run all gates (structure guard + SoT + duplicate guard + pytest)
python 12_tooling/cli/run_all_gates.py
```

---

## Gate Sequence

Fixed order, stop-on-first-failure:

1. **ROOT-24-LOCK**: Verifies exactly 24 numbered root modules.
2. **Git status clean**: Working tree must be clean (CI: clean workspace).
3. **SoT Verify**: Runs `sot_validator.py --verify-all`. Must exist and pass.
4. **pytest**: Runs `pytest -q` scoped to tooling tests.
5. **Evidence write test**: Confirms evidence.json can be written deterministically.

When a gate fails, the sequence stops immediately. Fix the failing gate before
proceeding -- later gates will not run until earlier ones pass.

---

## CI vs Local

| Aspect | Local | CI |
|--------|-------|----|
| **Invocation** | `python 12_tooling/cli/stability_gate.py --run` | Triggered automatically on PR push |
| **Working directory** | Your repo checkout | Fresh clone of the PR branch |
| **Git status** | Must be clean (commit first) | Always clean (fresh checkout) |
| **ROOT-24-LOCK** | Checks your working tree | Checks cloned tree |
| **pytest temp dir** | Default OS temp or `--basetemp` override | Configured via workflow YAML |
| **Evidence output** | Written to local `02_audit_logging/` | Written to CI workspace `02_audit_logging/` |
| **Failure behavior** | Prints FAIL to stdout, exits non-zero | Fails the PR check, blocks merge |
| **OPA policy checks** | Optional (if OPA installed) | Required (installed in CI image) |
| **Typical use** | Pre-push validation | Merge gate |

**Recommendation:** Always run the stability gate locally before pushing to catch
failures early. CI failures require a new commit and push cycle.

---

## Workspace Paths

Evidence and gate artifacts use the standard SSID workspace layout.

| Environment | Workspace Root | Example Worktree |
|-------------|---------------|------------------|
| **Windows (native)** | `${HOME} | `${HOME} |
| **WSL / Linux** | `~/.ssid/worktrees/` | `~/.ssid/worktrees/<TASK_ID>` |
| **Codespaces** | `~/.ssid/worktrees/` | `~/.ssid/worktrees/<TASK_ID>` |

Gate evidence is written to `02_audit_logging/agent_runs/STABILITY_GATE/<UTC>/evidence.json`
within the repo. The workspace root above is for agent scratch files, not gate
output.

---

## Output

- stdout: `PASS` or `FAIL` with concrete findings per gate.
- Evidence: `02_audit_logging/agent_runs/STABILITY_GATE/<UTC>/evidence.json`

---

## Troubleshooting: General

| Symptom | Cause | Fix |
|---------|-------|-----|
| "Expected 24 roots, found N" | ROOT-24-LOCK violated | Remove unauthorized root dirs/files. Only the 24 numbered directories (`01_ai_layer/` through `24_meta_orchestration/`) plus repo config files are allowed at root. |
| "Git status not clean" | Uncommitted changes | Commit pending changes: `git add <files> && git commit`. |
| "sot_validator.py not found" | Missing tool | Verify file exists at `12_tooling/cli/sot_validator.py`. Pull latest main if missing. |
| "pytest failed" | Test failures | Run `pytest -v` for detailed output. Check individual test files for assertion messages. |
| "Evidence write failed" | Permission or path issue | Check `02_audit_logging/` is writable. Run `automation_loop.py --init` to recreate directories. |
| "OPA not installed" / `opa: command not found` | OPA binary not on PATH | Install OPA locally: download from the OPA releases page and add to PATH. In CI, the workflow installs it automatically. Locally, this gate may be optional. |
| Test timeout (pytest hangs) | Long-running or deadlocked test | Run `pytest -v --timeout=30` to add per-test timeouts. Check for infinite loops or network calls in tests. If using `--basetemp`, ensure the temp path is writable and on a fast filesystem. |
| "Permission denied" writing evidence | Insufficient write access to audit directory | On Linux/macOS: `chmod -R u+w 02_audit_logging/`. On Windows: check folder properties. Ensure no other process holds a lock on the directory. |
| "ROOT-24-LOCK" passes locally, fails in CI | Hidden files or OS-generated directories | Check for `.DS_Store`, `Thumbs.db`, or other OS artifacts at root. Add them to `.gitignore`. |
| All gates pass locally, CI still fails | Environment difference | Compare Python version (`python --version`), installed packages (`pip list`), and OS. CI may enforce stricter checks. |
| "SoT hash mismatch" | Source-of-truth file was edited without updating the hash | Re-run `sot_validator.py` to identify which file changed. Regenerate hashes after intentional edits. |
| Gate fails with no clear error | stdout truncated or redirected | Run with `python 12_tooling/cli/stability_gate.py --run 2>&1` to capture both stdout and stderr. |

---

## Troubleshooting: Windows

Issues specific to running the stability gate on Windows (native or Git Bash).

| Symptom | Cause | Fix |
|---------|-------|-----|
| `ls -d [0-9][0-9]_*/` fails in PowerShell | PowerShell does not support glob syntax | Use Git Bash for all gate commands, or run via `python 12_tooling/cli/stability_gate.py --run` which handles this internally. |
| "Permission denied" writing evidence | Windows file locking (antivirus, editor) | Close editors/IDEs that may lock files in `02_audit_logging/`. Retry after a few seconds. Exclude the repo from real-time antivirus scanning if safe to do so. |
| pytest `basetemp` errors | Default temp path too long or locked | Use `--basetemp` to set a short temp path: `python -m pytest -q --basetemp=C:/tmp/pytest`. Avoid paths with spaces. |
| `python` not found | Python launcher aliasing | In Git Bash, use `python`. In PowerShell/cmd, use `python` or `py -3`. Verify with `python --version`. |
| `UnicodeDecodeError` during gate run | Non-UTF-8 locale | Set `PYTHONUTF8=1`: `set PYTHONUTF8=1` (cmd) or `$env:PYTHONUTF8=1` (PowerShell). |
| `subprocess.CalledProcessError` on gate checks | Required binary not on PATH | Ensure `python` is on PATH. For OPA, download the Windows binary and add its folder to PATH. |

---

## Troubleshooting: WSL

Issues specific to running the stability gate under Windows Subsystem for Linux.

| Symptom | Cause | Fix |
|---------|-------|-----|
| `python3` works but `python` does not | Debian/Ubuntu default | Install `python-is-python3`: `sudo apt install python-is-python3`, or create a symlink: `sudo ln -s /usr/bin/python3 /usr/bin/python`. |
| Git shows all files as modified | WSL mounts NTFS without Unix permissions | Set `git config core.fileMode false`. Or clone into WSL filesystem (`~/projects/SSID`). |
| Slow gate execution on `/mnt/c/` | NTFS access through WSL is slow | Clone into native WSL filesystem. File operations are 5-10x faster on ext4. |
| ROOT-24-LOCK count is wrong | Hidden files from Windows side | Run `ls -d [0-9][0-9]_*/` to see what is counted. Remove unexpected entries. Check for `.DS_Store` or `Thumbs.db` at root. |
| Wrong Python resolves (Windows Python) | WSL PATH includes `/mnt/c/` Windows paths | Configure `/etc/wsl.conf` with `[interop] appendWindowsPath=false`, or filter PATH in `~/.bashrc`. |

---

## Troubleshooting: Codespaces

Issues specific to running the stability gate in GitHub Codespaces.

| Symptom | Cause | Fix |
|---------|-------|-----|
| Evidence directory permission denied | Container user does not own audit directories | Run `sudo chown -R $(whoami) 02_audit_logging/` once after first clone. |
| OPA binary not available | Not pre-installed in container | Download the Linux binary from the OPA releases page and add to PATH. Or add to `devcontainer.json` features. |
| pytest discovers tests from unexpected paths | Container has different working directory | Always run from repo root: `cd /workspaces/SSID && python 12_tooling/cli/stability_gate.py --run`. |
| Git identity not set | Codespace does not inherit local config | Set: `git config user.name "<name>"` and `git config user.email "<email>"`. |
| Prebuild cache stale | Old prebuild missing recent gate changes | Rebuild container via Command Palette > "Codespaces: Rebuild Container". |
