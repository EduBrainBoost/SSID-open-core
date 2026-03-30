# DEPRECATED: REDUNDANT — Canonical tool is 12_tooling/cli/report_aggregator.py
# Dependencies: 11_test_simulation/tests_compliance/test_report_bus.py,
#   12_tooling/cli/evidence_chain.py, 12_tooling/cli/run_all_gates.py,
#   12_tooling/ops/evidence_chain/evidence_chain_lib.py
#!/usr/bin/env python3
"""
SSID Report Bus v2 — Event-store model with deterministic rebuild.

Events are stored as individual JSON files in 24_meta_orchestration/report_bus/events/.
The derived report_bus.jsonl is rebuilt deterministically from events/ (sorted by
observed_utc, then event_id).

Commands:
  append           Append a single event (creates EVENT file + rebuilds JSONL)
  rebuild          Rebuild report_bus.jsonl from events/ (idempotent)
  migrate-legacy   Migrate legacy JSONL events to individual EVENT files
  ingest           Ingest from existing source file (e2e_run, run_log)

Output contract: PASS/FAIL + findings only. No scores. Deterministic JSON.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVENTS_DIR = PROJECT_ROOT / "24_meta_orchestration" / "report_bus" / "events"
DERIVED_JSONL = PROJECT_ROOT / "24_meta_orchestration" / "report_bus" / "report_bus.jsonl"
LEGACY_INBOX = PROJECT_ROOT / "02_audit_logging" / "inbox" / "report_bus.jsonl"
LEGACY_ARCHIVE = PROJECT_ROOT / "02_audit_logging" / "archives" / "report_bus_legacy"

VALID_REPOS = ("SSID", "SSID-EMS", "SSID-docs", "SSID-open-core", "SSID-orchestrator")
VALID_EVENT_TYPES = (
    "merge_recorded", "agent_run_backfilled", "evidence_imported",
    "task_linked", "seal_merge", "docs_publish_merge", "ops", "legacy_migrated",
)
VALID_ORIGINS = ("observed", "constructed", "imported")
VALID_SEVERITIES = ("info", "warn", "error", "critical")


def _utc_now() -> str:
    return (
        dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def compute_event_id(event: dict[str, Any]) -> str:
    canonical_fields = {k: v for k, v in event.items() if k != "event_id"}
    canonical = json.dumps(canonical_fields, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def get_head_sha(repo_root: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(repo_root), capture_output=True, text=True, timeout=5,
        )
        return proc.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def make_event(
    *,
    event_type: str,
    repo: str,
    sha: str,
    origin: str,
    severity: str,
    summary: str,
    merge_sha: str | None = None,
    pr_number: int | None = None,
    task_id: str | None = None,
    observed_utc: str | None = None,
    refs: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event = {
        "event_type": event_type,
        "merge_sha": merge_sha,
        "observed_utc": observed_utc or _utc_now(),
        "origin": origin,
        "payload": payload or {},
        "pr_number": pr_number,
        "refs": refs or {},
        "repo": repo,
        "severity": severity,
        "sha": sha,
        "summary": summary[:200],
        "task_id": task_id,
    }
    event["event_id"] = compute_event_id(event)
    return event


def validate_event(event: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = ("event_id", "event_type", "repo", "sha", "origin", "observed_utc", "severity", "summary")
    for key in required:
        if key not in event:
            errors.append(f"missing required field: {key}")
    if event.get("event_type") and event["event_type"] not in VALID_EVENT_TYPES:
        errors.append(f"invalid event_type: {event['event_type']!r}")
    if event.get("repo") and event["repo"] not in VALID_REPOS:
        errors.append(f"invalid repo: {event['repo']!r}")
    if event.get("origin") and event["origin"] not in VALID_ORIGINS:
        errors.append(f"invalid origin: {event['origin']!r}")
    if event.get("severity") and event["severity"] not in VALID_SEVERITIES:
        errors.append(f"invalid severity: {event['severity']!r}")
    if "observed_utc" in event:
        ts = event["observed_utc"]
        if not isinstance(ts, str) or not re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", ts):
            errors.append(f"invalid observed_utc format: {ts!r}")
    if "event_id" in event:
        eid = event["event_id"]
        if not isinstance(eid, str) or not re.match(r"^[0-9a-f]{64}$", eid):
            errors.append(f"invalid event_id: {eid!r}")
    return errors


def write_event(event: dict[str, Any], events_dir: Path | None = None) -> Path:
    errors = validate_event(event)
    if errors:
        raise ValueError(f"Invalid event: {'; '.join(errors)}")
    d = events_dir or EVENTS_DIR
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"EVENT_{event['event_id'][:16]}.json"
    path.write_text(
        json.dumps(event, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def load_all_events(events_dir: Path | None = None) -> list[dict[str, Any]]:
    d = events_dir or EVENTS_DIR
    if not d.is_dir():
        return []
    events = []
    for f in d.glob("EVENT_*.json"):
        try:
            events.append(json.loads(f.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"WARN: skipping {f.name}: {exc}", file=sys.stderr)
    events.sort(key=lambda e: (e.get("observed_utc", ""), e.get("event_id", "")))
    return events


def rebuild_jsonl(events_dir: Path | None = None, output_path: Path | None = None) -> Path:
    events = load_all_events(events_dir)
    out = output_path or DERIVED_JSONL
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(e, sort_keys=True, ensure_ascii=False) for e in events]
    out.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return out


def _map_legacy_kind_to_event_type(kind: str) -> str:
    return {"seal_merge": "seal_merge", "docs_publish_merge": "docs_publish_merge", "ops": "ops"}.get(kind, "legacy_migrated")


def migrate_legacy_events(
    legacy_path: Path | None = None,
    events_dir: Path | None = None,
    archive_dir: Path | None = None,
    write: bool = False,
) -> dict[str, Any]:
    lp = legacy_path or LEGACY_INBOX
    ed = events_dir or EVENTS_DIR
    ad = archive_dir or LEGACY_ARCHIVE
    if not lp.is_file():
        return {"status": "SKIP", "reason": "legacy file not found", "migrated": 0}
    legacy_lines = [l.strip() for l in lp.read_text(encoding="utf-8").splitlines() if l.strip()]
    migrated = []
    for i, line in enumerate(legacy_lines, 1):
        try:
            old = json.loads(line)
        except json.JSONDecodeError:
            print(f"WARN: skipping invalid JSON at line {i}", file=sys.stderr)
            continue
        event = make_event(
            event_type=_map_legacy_kind_to_event_type(old.get("kind", "")),
            repo=old.get("repo", "SSID"),
            sha=old.get("sha", "unknown"),
            origin="imported",
            severity=old.get("severity", "info"),
            summary=old.get("summary", f"Legacy event line {i}")[:200],
            observed_utc=old.get("ts_utc", _utc_now()),
            payload=old.get("payload", {}),
        )
        migrated.append(event)
        if write:
            write_event(event, ed)
    if write and migrated:
        ad.mkdir(parents=True, exist_ok=True)
        legacy_hash = hashlib.sha256(lp.read_bytes()).hexdigest()[:16]
        shutil.copy2(str(lp), str(ad / f"REPORT_BUS_LEGACY_{legacy_hash}.jsonl"))
    return {"status": "PASS", "legacy_lines": len(legacy_lines), "migrated": len(migrated), "write_mode": write}


def ingest_e2e_run(path: Path, sha: str | None = None) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    run_sha = sha or data.get("git_sha", "unknown")
    status = data.get("status", "unknown")
    return [make_event(
        event_type="evidence_imported", repo="SSID", sha=run_sha, origin="imported",
        severity="info" if status == "PASS" else "error",
        summary=f"E2E run {data.get('run_id', '?')}: {status}",
        payload={"run_id": data.get("run_id"), "status": status, "source_file": path.name},
    )]


def ingest_run_log(path: Path, sha: str | None = None) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").strip().splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        events.append(make_event(
            event_type="evidence_imported", repo="SSID",
            sha=sha or entry.get("sha", "unknown"), origin="imported",
            severity="info", summary=f"Run log: {entry.get('event', 'unknown')}",
            payload=entry,
        ))
    return events


def _cli_append(args: argparse.Namespace) -> int:
    event = make_event(
        event_type=args.event_type, repo=args.repo, sha=args.sha,
        origin=args.origin, severity=args.severity, summary=args.summary,
        payload=json.loads(args.payload) if args.payload else {},
    )
    try:
        path = write_event(event)
        rebuild_jsonl()
        print(f"OK: event {event['event_id'][:16]} written to {path.name}")
        print(f"OK: report_bus.jsonl rebuilt")
        return 0
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


def _cli_rebuild(args: argparse.Namespace) -> int:
    events = load_all_events()
    out = rebuild_jsonl()
    print(f"OK: rebuilt {out} from {len(events)} events")
    if args.verify:
        content1 = out.read_text(encoding="utf-8")
        rebuild_jsonl()
        content2 = out.read_text(encoding="utf-8")
        if content1 == content2:
            print("PASS: rebuild is idempotent")
            return 0
        else:
            print("FAIL: rebuild is NOT idempotent", file=sys.stderr)
            return 1
    return 0


def _cli_migrate_legacy(args: argparse.Namespace) -> int:
    result = migrate_legacy_events(write=args.write)
    print(json.dumps(result, indent=2))
    if result["status"] == "PASS" and args.write:
        rebuild_jsonl()
        print("OK: report_bus.jsonl rebuilt after migration")
    return 0 if result["status"] in ("PASS", "SKIP") else 1


def _cli_ingest(args: argparse.Namespace) -> int:
    source_path = Path(args.file)
    if not source_path.exists():
        print(f"ERROR: file not found: {source_path}", file=sys.stderr)
        return 1
    adapter_map = {"e2e_run": ingest_e2e_run, "run_log": ingest_run_log}
    adapter = adapter_map.get(args.adapter)
    if adapter is None:
        print(f"ERROR: unknown adapter: {args.adapter!r}", file=sys.stderr)
        return 1
    events = adapter(source_path, sha=args.sha)
    count = 0
    for ev in events:
        try:
            write_event(ev)
            count += 1
        except ValueError as exc:
            print(f"WARN: skipping invalid event: {exc}", file=sys.stderr)
    if count > 0:
        rebuild_jsonl()
    print(f"OK: ingested {count} event(s) from {source_path.name}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="report_bus",
        description="SSID Report Bus v2 — event-store with deterministic rebuild.",
    )
    sub = parser.add_subparsers(dest="command")

    ap = sub.add_parser("append", help="Append a single event.")
    ap.add_argument("--repo", required=True, choices=VALID_REPOS)
    ap.add_argument("--sha", required=True)
    ap.add_argument("--event-type", required=True, choices=VALID_EVENT_TYPES)
    ap.add_argument("--origin", required=True, choices=VALID_ORIGINS)
    ap.add_argument("--severity", required=True, choices=VALID_SEVERITIES)
    ap.add_argument("--summary", required=True)
    ap.add_argument("--payload", default=None, help="JSON object string")

    rp = sub.add_parser("rebuild", help="Rebuild report_bus.jsonl from events/.")
    rp.add_argument("--verify", action="store_true", help="Verify idempotency")

    mp = sub.add_parser("migrate-legacy", help="Migrate legacy JSONL to event store.")
    mp.add_argument("--write", action="store_true", help="Actually write files")

    ip = sub.add_parser("ingest", help="Ingest events from an existing source file.")
    ip.add_argument("--adapter", required=True, choices=["e2e_run", "run_log"])
    ip.add_argument("--file", required=True, help="Path to source file")
    ip.add_argument("--sha", default=None, help="Override SHA for all events")

    args = parser.parse_args()
    cmd_map = {"append": _cli_append, "rebuild": _cli_rebuild, "migrate-legacy": _cli_migrate_legacy, "ingest": _cli_ingest}
    handler = cmd_map.get(args.command)
    if handler:
        return handler(args)
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
