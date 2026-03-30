"""Shared event I/O for Report Bus v2.

Provides read/write operations for individual EVENT_*.json files
and JSONL rebuild from event store.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EVENTS_DIR_NAME = "events"
REPORT_BUS_JSONL = "report_bus.jsonl"


def compute_event_id(event: dict[str, Any]) -> str:
    """Compute deterministic SHA-256 event_id from canonical fields."""
    canonical = json.dumps(
        {k: event[k] for k in sorted(event) if k != "event_id"},
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def emit_event(
    events_dir: Path,
    *,
    repo: str,
    sha: str,
    source: str,
    kind: str,
    severity: str = "info",
    summary: str,
    origin: str = "observed",
    payload: dict[str, Any] | None = None,
) -> Path:
    """Write a single event to the event store. Returns path to created file."""
    ts_utc = datetime.now(timezone.utc).isoformat()
    event: dict[str, Any] = {
        "ts_utc": ts_utc,
        "repo": repo,
        "sha": sha,
        "source": source,
        "kind": kind,
        "severity": severity,
        "summary": summary,
        "origin": origin,
    }
    if payload:
        event["payload"] = payload

    event["event_id"] = compute_event_id(event)

    events_dir.mkdir(parents=True, exist_ok=True)
    filename = f"EVENT_{event['event_id'][:16]}_{ts_utc.replace(':', '').replace('-', '')[:15]}.json"
    path = events_dir / filename
    path.write_text(
        json.dumps(event, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def load_events(events_dir: Path) -> list[dict[str, Any]]:
    """Load all events from the event store, sorted by timestamp."""
    events: list[dict[str, Any]] = []
    if not events_dir.exists():
        return events
    for f in sorted(events_dir.glob("EVENT_*.json")):
        try:
            event = json.loads(f.read_text(encoding="utf-8"))
            events.append(event)
        except (json.JSONDecodeError, OSError):
            continue
    events.sort(key=lambda e: e.get("ts_utc", ""))
    return events


def rebuild_jsonl(events_dir: Path, output_path: Path) -> int:
    """Rebuild report_bus.jsonl from individual event files. Returns event count."""
    events = load_events(events_dir)
    lines = [json.dumps(e, sort_keys=True, ensure_ascii=False) for e in events]
    output_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return len(events)


def validate_event(event: dict[str, Any]) -> list[str]:
    """Validate event against schema v2 rules. Returns list of errors."""
    errors: list[str] = []
    required = ["event_id", "ts_utc", "repo", "sha", "source", "kind", "severity", "summary"]
    for field in required:
        if field not in event:
            errors.append(f"missing required field: {field}")

    if "event_id" in event:
        expected = compute_event_id(event)
        if event["event_id"] != expected:
            errors.append(f"event_id mismatch: stored={event['event_id'][:16]}... expected={expected[:16]}...")

    valid_kinds = {"gate_pass", "gate_fail", "evidence_created", "pr_merged", "backfill", "migration", "manual"}
    if event.get("kind") not in valid_kinds:
        errors.append(f"invalid kind: {event.get('kind')}")

    valid_severities = {"info", "warning", "error", "critical"}
    if event.get("severity") not in valid_severities:
        errors.append(f"invalid severity: {event.get('severity')}")

    valid_origins = {"observed", "constructed", "imported"}
    if event.get("origin") and event["origin"] not in valid_origins:
        errors.append(f"invalid origin: {event['origin']}")

    return errors
