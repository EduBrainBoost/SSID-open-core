"""Evidence Chain Library v2 — PR-merge-only backfill for SSID audit compliance.

Scans git history (first-parent), detects existing agent_runs + report_bus events,
and generates missing artifacts for PR merges only (additive, idempotent).

All backfill artifacts are marked origin=constructed (retroactive, no agent claims).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "cli"))
import report_bus as rb


def git_first_parent_commits(repo: Path, limit: int = 200) -> list[dict[str, Any]]:
    raw = subprocess.check_output(
        ["git", "log", "--first-parent", f"-n{limit}", "--pretty=format:%H|%cI|%s"],
        cwd=str(repo),
        text=True,
        errors="replace",
    ).strip()
    if not raw:
        return []
    results = []
    for line in raw.splitlines():
        parts = line.split("|", 2)
        if len(parts) < 3:
            continue
        sha, date_str, subject = parts
        results.append({"merge_sha": sha, "commit_date_utc": _normalize_date(date_str), "subject": subject})
    return results


def _normalize_date(date_str: str) -> str:
    try:
        d = datetime.fromisoformat(date_str)
        return d.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (ValueError, TypeError):
        return date_str


def git_diff_stat(repo: Path, sha: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "diff", f"{sha}~1..{sha}", "--stat"],
            cwd=str(repo),
            text=True,
            errors="replace",
            timeout=30,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return ""


def git_show_header(repo: Path, sha: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "show", "-s", "--format=commit %H%nAuthor: %an <%ae>%nDate: %cI%nSubject: %s%n%nParents: %P", sha],
            cwd=str(repo),
            text=True,
            errors="replace",
        )
    except subprocess.CalledProcessError:
        return ""


def extract_pr_number(subject: str) -> int | None:
    m = re.search(r"Merge pull request #(\d+)", subject)
    if m:
        return int(m.group(1))
    m = re.search(r"\(#(\d+)\)\s*$", subject)
    if m:
        return int(m.group(1))
    return None


def extract_task_id(subject: str) -> str | None:
    for pat in [r"(TS\d{3})", r"(PH[23]_[A-Z_]+_\d{3})", r"(P1_[A-Z_]+_\d{3})", r"(POC_[A-Z_]+_\d{3})"]:
        m = re.search(pat, subject, re.IGNORECASE)
        if m:
            return m.group(1).upper()
    known = {"ts013": "TS013", "ts014": "TS014", "ts015": "TS015", "ts016": "TS016", "ts018": "TS018", "ts030": "TS030"}
    lower = subject.lower()
    for k, v in known.items():
        if k in lower:
            return v
    return None


def find_existing_report_bus_shas(repo: Path) -> set[str]:
    shas: set[str] = set()
    events_dir = repo / "24_meta_orchestration" / "report_bus" / "events"
    if events_dir.is_dir():
        for f in events_dir.glob("EVENT_*.json"):
            try:
                event = json.loads(f.read_text(encoding="utf-8"))
                sha = event.get("sha", "")
                if sha:
                    shas.add(sha)
                    if len(sha) >= 7:
                        shas.add(sha[:7])
            except Exception:
                continue
    bus_file = repo / "02_audit_logging" / "inbox" / "report_bus.jsonl"
    if bus_file.is_file():
        for line in bus_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                event = json.loads(line)
                sha = event.get("sha", "")
                if sha:
                    shas.add(sha)
                    if len(sha) >= 7:
                        shas.add(sha[:7])
            except Exception:
                continue
    return shas


def find_existing_agent_runs(repo: Path) -> set[str]:
    shas: set[str] = set()
    agent_runs = repo / "02_audit_logging" / "agent_runs"
    if not agent_runs.is_dir():
        return shas
    for d in agent_runs.iterdir():
        if d.is_dir() and d.name.startswith("run-merge-"):
            sha7 = d.name.replace("run-merge-", "")
            if len(sha7) >= 7:
                shas.add(sha7)
    for item in agent_runs.rglob("*.json"):
        try:
            data = json.loads(item.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                continue
            for key in ("sha", "commit", "merge_sha", "merge_commit", "head_sha"):
                v = data.get(key)
                if isinstance(v, str) and len(v) >= 7:
                    shas.add(v)
                    shas.add(v[:7])
        except Exception:
            continue
    return shas


def scan(repo: Path, limit: int = 200, pr_only: bool = False) -> dict[str, Any]:
    commits = git_first_parent_commits(repo, limit)
    existing_runs = find_existing_agent_runs(repo)
    existing_events = find_existing_report_bus_shas(repo)
    entries = []
    missing_runs = []
    missing_events = []
    for c in commits:
        sha = c["merge_sha"]
        sha7 = sha[:7]
        pr = extract_pr_number(c["subject"])
        task = extract_task_id(c["subject"])
        if pr_only and pr is None:
            continue
        has_run = sha in existing_runs or sha7 in existing_runs
        has_event = sha in existing_events or sha7 in existing_events
        entry = {
            "merge_sha": sha,
            "commit_date_utc": c["commit_date_utc"],
            "subject": c["subject"],
            "pr_number": pr,
            "task_id": task,
            "has_agent_run": has_run,
            "has_report_event": has_event,
        }
        entries.append(entry)
        if not has_run:
            missing_runs.append(entry)
        if not has_event:
            missing_events.append(entry)
    return {
        "total_commits": len(entries),
        "commits_with_agent_run": len(entries) - len(missing_runs),
        "commits_with_report_event": len(entries) - len(missing_events),
        "missing_agent_runs": len(missing_runs),
        "missing_report_events": len(missing_events),
        "entries": entries,
    }


def backfill_pr_merges(
    repo: Path, scan_result: dict[str, Any], write: bool = False, now_utc: str | None = None
) -> dict[str, Any]:
    if now_utc is None:
        now_utc = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    agent_runs_base = repo / "02_audit_logging" / "agent_runs"
    events_dir = repo / "24_meta_orchestration" / "report_bus" / "events"
    created_runs: list[str] = []
    created_events: list[str] = []
    gaps: list[dict[str, Any]] = []
    for entry in scan_result["entries"]:
        sha = entry["merge_sha"]
        sha7 = sha[:7]
        pr = entry["pr_number"]
        task = entry["task_id"]
        run_id = f"run-merge-{sha7}"
        run_dir = agent_runs_base / run_id
        if not entry["has_agent_run"]:
            if write:
                run_dir.mkdir(parents=True, exist_ok=True)
                manifest = {
                    "backfill_date_utc": now_utc,
                    "commit_date_utc": entry["commit_date_utc"],
                    "merge_sha": sha,
                    "origin": "constructed",
                    "pr_number": pr,
                    "repo": "SSID",
                    "run_id": run_id,
                    "subject": entry["subject"],
                    "task_id": task,
                }
                (run_dir / "run_manifest.json").write_text(
                    json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
                )
                (run_dir / "diff_stat.txt").write_text(git_diff_stat(repo, sha), encoding="utf-8")
                (run_dir / "git_show.txt").write_text(git_show_header(repo, sha), encoding="utf-8")
                attestation = (
                    f"# Attestation: {run_id}\n\nRetroactively generated by evidence_chain backfill.\n\n"
                    f"- **Origin**: constructed (no agent execution claim)\n"
                    f"- **Source**: git commit `{sha}` (PR #{pr})\n"
                    f"- **Backfill date**: {now_utc}\n"
                    f"- **Original commit date**: {entry['commit_date_utc']}\n"
                )
                (run_dir / "attestation.md").write_text(attestation, encoding="utf-8")
            created_runs.append(str(run_dir.relative_to(repo)))
            entry["has_agent_run"] = True
        if not entry["has_report_event"]:
            event = rb.make_event(
                event_type="merge_recorded",
                repo="SSID",
                sha=sha,
                merge_sha=sha,
                pr_number=pr,
                task_id=task,
                origin="constructed",
                severity="info",
                summary=entry["subject"][:200],
                observed_utc=entry["commit_date_utc"],
                refs={"agent_run": f"02_audit_logging/agent_runs/{run_id}/run_manifest.json"},
                payload={"backfill": True, "backfill_date_utc": now_utc},
            )
            if write:
                rb.write_event(event, events_dir)
            created_events.append(event["event_id"][:16])
            entry["has_report_event"] = True
        if task is None:
            gaps.append(
                {
                    "merge_sha": sha[:7],
                    "pr_number": pr,
                    "reason": "task_id unresolved",
                    "subject": entry["subject"][:80],
                }
            )
    return {
        "created_agent_runs": created_runs,
        "created_events": created_events,
        "unresolved_gaps": gaps,
        "write_mode": write,
    }


def build_execution_index(repo: Path, scan_result: dict[str, Any], now_utc: str | None = None) -> dict[str, Any]:
    if now_utc is None:
        now_utc = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "version": "2.0",
        "repo": "SSID",
        "generated_utc": now_utc,
        "scope": "pr_merges_only",
        "entries": scan_result["entries"],
    }


def write_execution_index(repo: Path, index: dict[str, Any]) -> str:
    out = repo / "24_meta_orchestration" / "registry" / "execution_index.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(index, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return str(out.relative_to(repo))


def write_gap_report(repo: Path, backfill_result: dict[str, Any]) -> str:
    out = repo / "02_audit_logging" / "reports" / "EVIDENCE_CHAIN_GAPS_MERGES_V1.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(backfill_result["unresolved_gaps"], indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return str(out.relative_to(repo))
