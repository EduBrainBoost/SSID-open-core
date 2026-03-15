"""PulseStateStore — file-based JSONL storage for PulseMetrics snapshots.

No database dependency. Thread-safe append via exclusive file locking
(falls back to non-locked writes when portalocker is unavailable).

Storage layout::

    <store_dir>/
        pulse_history.jsonl   — append-only ring buffer (capped at MAX_LINES)
        latest.json           — most-recent pulse snapshot

Default store_dir: ``~/.ssid/pulse_store``
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_STORE_DIR = Path.home() / ".ssid" / "pulse_store"
_HISTORY_FILE = "pulse_history.jsonl"
_LATEST_FILE = "latest.json"
_MAX_LINES = 10_000  # cap to avoid unbounded growth


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


class PulseStateStore:
    """Append-only JSONL store for PulseMetrics snapshots."""

    def __init__(self, store_dir: Path | str | None = None) -> None:
        self._store_dir = Path(store_dir) if store_dir else _DEFAULT_STORE_DIR
        self._store_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save_pulse(self, pulse_data: Any) -> str:
        """Persist a PulseMetrics (or dict) snapshot.

        Returns the SHA-256 hash of the serialised record so callers can
        reference it deterministically.
        """
        record = self._to_dict(pulse_data)
        record.setdefault("stored_at", _utcnow_iso())
        serialised = json.dumps(record, default=str)
        digest = _sha256(serialised)
        record["_hash"] = digest

        line = json.dumps(record, default=str)
        self._append_line(line)
        self._write_latest(record)
        return digest

    def get_latest_pulse(self) -> dict[str, Any] | None:
        """Return the most-recently stored pulse snapshot, or None."""
        path = self._store_dir / _LATEST_FILE
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            logger.debug("Could not read latest pulse", exc_info=True)
            return None

    def get_pulse_history(self, count: int = 100) -> list[dict[str, Any]]:
        """Return the last *count* pulse records in chronological order (oldest first)."""
        path = self._store_dir / _HISTORY_FILE
        if not path.is_file():
            return []
        lines = self._read_lines(path)
        # Take the last `count` lines and parse
        tail = lines[-count:] if len(lines) > count else lines
        records: list[dict[str, Any]] = []
        for line in tail:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                logger.debug("Skipping malformed JSONL line")
        return records

    def clear(self) -> None:
        """Remove all stored pulse data (useful for tests)."""
        for fname in (_HISTORY_FILE, _LATEST_FILE):
            path = self._store_dir / fname
            try:
                if path.is_file():
                    path.unlink()
            except Exception:
                logger.debug("Could not remove %s", path, exc_info=True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_dict(pulse_data: Any) -> dict[str, Any]:
        if isinstance(pulse_data, dict):
            return dict(pulse_data)
        if hasattr(pulse_data, "to_dict"):
            return pulse_data.to_dict()
        if hasattr(pulse_data, "__dataclass_fields__"):
            from dataclasses import asdict
            return asdict(pulse_data)
        return {"raw": str(pulse_data)}

    def _append_line(self, line: str) -> None:
        """Append a single JSONL line; trims file to MAX_LINES if needed."""
        path = self._store_dir / _HISTORY_FILE
        try:
            self._safe_append(path, line)
            # Periodically trim — only when file is large
            if path.stat().st_size > 5 * 1024 * 1024:  # > 5 MB
                self._trim_history(path)
        except Exception:
            logger.debug("Could not append pulse line", exc_info=True)

    @staticmethod
    def _safe_append(path: Path, line: str) -> None:
        """Append a line with best-effort exclusive locking."""
        try:
            import portalocker  # type: ignore
            with portalocker.Lock(str(path), mode="a", encoding="utf-8", timeout=3) as fh:
                fh.write(line + "\n")
        except ImportError:
            # No portalocker — plain append (acceptable for single-process use)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")

    @staticmethod
    def _read_lines(path: Path) -> list[str]:
        try:
            return path.read_text(encoding="utf-8").splitlines()
        except Exception:
            return []

    def _trim_history(self, path: Path) -> None:
        """Keep only the last MAX_LINES lines (atomic rename)."""
        lines = self._read_lines(path)
        if len(lines) <= _MAX_LINES:
            return
        trimmed = lines[-_MAX_LINES:]
        tmp_path = path.with_suffix(".jsonl.tmp")
        try:
            tmp_path.write_text("\n".join(trimmed) + "\n", encoding="utf-8")
            tmp_path.replace(path)
        except Exception:
            logger.debug("Could not trim pulse history", exc_info=True)
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass

    def _write_latest(self, record: dict[str, Any]) -> None:
        """Atomically write the latest snapshot (write-to-tmp then rename)."""
        path = self._store_dir / _LATEST_FILE
        tmp_path = path.with_suffix(".json.tmp")
        try:
            tmp_path.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
            tmp_path.replace(path)
        except Exception:
            logger.debug("Could not write latest pulse", exc_info=True)
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass
