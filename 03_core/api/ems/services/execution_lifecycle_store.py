import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _runs_path(repo_root: Path) -> Path:
    return repo_root / "24_meta_orchestration" / "registry" / "ems_execution_runs.jsonl"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _json_sha256(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    items: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw:
            continue
        items.append(json.loads(raw))
    return items


def append_execution_run_record(repo_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    path = _runs_path(repo_root)
    record = dict(payload)
    record.setdefault("run_id", f"RUN-{uuid.uuid4().hex[:12].upper()}")
    record.setdefault("created_at_utc", _utc_now_iso())
    record["evidence_hash"] = _json_sha256(
        {key: value for key, value in record.items() if key != "evidence_hash"}
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
    return record


def list_execution_runs(repo_root: Path) -> list[dict[str, Any]]:
    items = _read_jsonl(_runs_path(repo_root))
    items.sort(key=lambda item: item.get("created_at_utc", ""), reverse=True)
    return items


def get_execution_run(repo_root: Path, run_id: str) -> dict[str, Any]:
    for item in list_execution_runs(repo_root):
        if item.get("run_id") == run_id:
            return item
    raise FileNotFoundError(f"execution_run_not_found: {run_id}")
