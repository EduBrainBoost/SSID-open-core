"""
session_watchdog.py - T-018 Agent Session Watchdog Gate
Hard TTL=65min, Orphan-Kill, Lock-File, SHA256-Logging
psutil is optional - PID checks degrade gracefully without it.
"""

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

try:
    import psutil
except ImportError:
    psutil = None

REPO_ROOT = Path(__file__).resolve().parents[2]
STATE_FILE = REPO_ROOT / "02_audit_logging" / "reports" / "session_state.json"
LOCK_FILE = REPO_ROOT / "02_audit_logging" / "reports" / "session_watchdog.lock"
REPORT_FILE = REPO_ROOT / "02_audit_logging" / "reports" / "agent_session_watchdog_report.json"
HARD_TTL_MINUTES = 65


def _sha256(data):
    return hashlib.sha256(data.encode()).hexdigest()


def _now_iso():
    return datetime.now(UTC).isoformat()


def _log_event(event_type, details):
    entry = {"timestamp": _now_iso(), "event": event_type, "details": details}
    entry["sha256"] = _sha256(json.dumps(entry, sort_keys=True))
    report = []
    if REPORT_FILE.exists():
        try:
            report = json.loads(REPORT_FILE.read_text())
        except Exception:
            report = []
    report.append(entry)
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text(json.dumps(report, indent=2))


def _read_state():
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {}


def _write_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def run_watchdog():
    """Main watchdog entrypoint. Returns result dict."""
    # Double-start protection
    if LOCK_FILE.exists():
        try:
            data = json.loads(LOCK_FILE.read_text())
            pid = data.get("pid")
            if pid and psutil is not None and psutil.pid_exists(pid):
                _log_event("DOUBLE_START_ABORT", {"existing_pid": pid})
                return {"status": "ABORTED", "reason": "double_start"}
            LOCK_FILE.unlink(missing_ok=True)
        except Exception:
            LOCK_FILE.unlink(missing_ok=True)

    # Write lock
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOCK_FILE.write_text(json.dumps({"pid": os.getpid(), "started": _now_iso()}))

    actions = []
    try:
        state = _read_state()

        # Orphan kill
        orphan_pid = state.get("orphan_pid") or state.get("pid")
        if orphan_pid:
            pid_alive = psutil.pid_exists(orphan_pid) if psutil is not None else False
            if not pid_alive:
                state.pop("orphan_pid", None)
                _write_state(state)
                _log_event("ORPHAN_CLEARED", {"pid": orphan_pid})
                actions.append("orphan_cleared")
            else:
                try:
                    psutil.Process(orphan_pid).terminate()
                    actions.append("orphan_killed")
                    _log_event("ORPHAN_KILLED", {"pid": orphan_pid})
                except Exception as e:
                    _log_event("ORPHAN_KILL_FAILED", {"pid": orphan_pid, "error": str(e)})

        # TTL check
        start_iso = state.get("session_started") or state.get("session_start")
        if start_iso:
            try:
                start = datetime.fromisoformat(start_iso)
                elapsed = (datetime.now(UTC) - start).total_seconds() / 60
                if elapsed > HARD_TTL_MINUTES:
                    _log_event("TTL_EXCEEDED", {"elapsed_minutes": round(elapsed, 1)})
                    _write_state({})
                    actions.append("state_reset")
            except Exception:
                pass

        result = {"status": "PASS", "actions": actions, "timestamp": _now_iso()}
        _log_event("WATCHDOG_PASS", {"actions": actions})
        return result

    finally:
        LOCK_FILE.unlink(missing_ok=True)


# alias
run_preflight = run_watchdog

if __name__ == "__main__":
    import sys

    result = run_watchdog()
    print(json.dumps(result))
    if result.get("status") == "ABORTED":
        sys.exit(1)
