"""In-memory key-value store with TTL and capacity limits."""

from __future__ import annotations

import datetime as dt
import threading
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SessionMemory:
    """Snapshot of a memory session's entries."""

    entries: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )
    last_accessed: str = field(
        default_factory=lambda: dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )


class MemoryManager:
    """Thread-safe in-memory key-value store with TTL and max_entries eviction.

    Parameters
    ----------
    max_entries : int
        Maximum number of entries before oldest are evicted (default 1024).
    default_ttl_seconds : int
        Default time-to-live for entries in seconds (default 3600).
    """

    def __init__(
        self,
        max_entries: int = 1024,
        default_ttl_seconds: int = 3600,
    ) -> None:
        self._max_entries = max_entries
        self._default_ttl = default_ttl_seconds
        self._store: dict[str, tuple[Any, float]] = {}  # key -> (value, expires_ts)
        self._insertion_order: list[str] = []
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def put(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        """Store a value. Evicts oldest entry if at capacity."""
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        expires = dt.datetime.now(dt.UTC).timestamp() + ttl
        with self._lock:
            if key in self._store:
                self._insertion_order.remove(key)
            self._store[key] = (value, expires)
            self._insertion_order.append(key)
            self._evict_if_needed()

    def get(self, key: str) -> Any | None:
        """Retrieve a value. Returns None if missing or expired."""
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expires = entry
            now = dt.datetime.now(dt.UTC).timestamp()
            if now > expires:
                self._remove_key(key)
                return None
            return value

    def delete(self, key: str) -> bool:
        """Remove a key. Returns True if it existed."""
        with self._lock:
            return self._remove_key(key)

    def snapshot(self) -> SessionMemory:
        """Return a SessionMemory snapshot of all non-expired entries."""
        with self._lock:
            now = dt.datetime.now(dt.UTC).timestamp()
            live: dict[str, Any] = {}
            expired_keys: list[str] = []
            for k, (v, exp) in self._store.items():
                if now > exp:
                    expired_keys.append(k)
                else:
                    live[k] = v
            for k in expired_keys:
                self._remove_key(k)
            return SessionMemory(entries=dict(live))

    @property
    def size(self) -> int:
        """Current number of entries (including possibly expired)."""
        return len(self._store)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _evict_if_needed(self) -> None:
        """Evict oldest entries to stay within max_entries."""
        while len(self._store) > self._max_entries and self._insertion_order:
            oldest = self._insertion_order[0]
            self._remove_key(oldest)

    def _remove_key(self, key: str) -> bool:
        if key in self._store:
            del self._store[key]
            if key in self._insertion_order:
                self._insertion_order.remove(key)
            return True
        return False
