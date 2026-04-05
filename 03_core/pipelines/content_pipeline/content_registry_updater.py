"""content_registry_updater.py — Sync KnowledgeIndex into knowledge_registry.json.

Reads the current registry (if any), merges new artifacts, and writes an
updated knowledge_registry.json in a deterministic, append-compatible format.

No PII; all hashes are SHA-256; output is deterministic given identical input.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .content_indexer import KnowledgeIndex
from .content_transformer import KnowledgeArtifact

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class RegistryEntry:
    """A single registry record for one knowledge artifact."""

    artifact_id: str
    title: str
    content_type: str
    primary_category: str
    categories: list[str]
    tags: list[str]
    source_path: str
    hash: str
    artifact_hash: str
    summary: str


@dataclass
class RegistryUpdate:
    """Result of an update_registry() call."""

    added: int
    updated: int
    unchanged: int
    total: int
    registry_hash: str  # SHA-256 of sorted artifact_ids in registry
    registry_path: str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_dict(data: dict[str, Any]) -> str:
    s = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(s).hexdigest()


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _entry_from_artifact(artifact: KnowledgeArtifact) -> RegistryEntry:
    primary = artifact.categories[0] if artifact.categories else "knowledge"
    return RegistryEntry(
        artifact_id=artifact.artifact_id,
        title=artifact.title,
        content_type=artifact.content_type,
        primary_category=primary,
        categories=list(artifact.categories),
        tags=list(artifact.tags),
        source_path=artifact.source_path,
        hash=artifact.hash,
        artifact_hash=artifact.artifact_hash,
        summary=artifact.summary,
    )


def _entry_to_dict(entry: RegistryEntry) -> dict[str, Any]:
    return {
        "artifact_id": entry.artifact_id,
        "title": entry.title,
        "content_type": entry.content_type,
        "primary_category": entry.primary_category,
        "categories": entry.categories,
        "tags": entry.tags,
        "source_path": entry.source_path,
        "hash": entry.hash,
        "artifact_hash": entry.artifact_hash,
        "summary": entry.summary,
    }


# ---------------------------------------------------------------------------
# ContentRegistryUpdater
# ---------------------------------------------------------------------------


class ContentRegistryUpdater:
    """
    Merges a KnowledgeIndex into knowledge_registry.json.

    The registry stores a lightweight summary of all known artifacts for
    fast lookup without loading full bodies.  It is append-compatible:
    existing entries are updated if their artifact_hash changed, otherwise
    they are left unchanged.

    All operations are deterministic given identical inputs.
    """

    DEFAULT_FILENAME = "knowledge_registry.json"

    def update_registry(
        self,
        index: KnowledgeIndex,
        registry_path: str,
    ) -> RegistryUpdate:
        """
        Merge all artifacts in index into the registry at registry_path.

        Args:
            index: KnowledgeIndex produced by ContentIndexer.build_index().
            registry_path: Full path to knowledge_registry.json, or a
                           directory (DEFAULT_FILENAME appended automatically).

        Returns:
            RegistryUpdate with counts (added / updated / unchanged) and
            the new registry_hash.
        """
        reg_path = Path(registry_path)
        if reg_path.is_dir():
            reg_path = reg_path / self.DEFAULT_FILENAME

        # Load existing registry
        existing: dict[str, dict[str, Any]] = {}
        if reg_path.exists():
            try:
                data = json.loads(reg_path.read_text(encoding="utf-8"))
                for entry in data.get("entries", []):
                    existing[entry["artifact_id"]] = entry
            except Exception as exc:
                logger.warning("update_registry: cannot read existing registry: %s", exc)

        added = 0
        updated = 0
        unchanged = 0

        for artifact in index.artifacts:
            entry = _entry_from_artifact(artifact)
            entry_dict = _entry_to_dict(entry)
            existing_entry = existing.get(artifact.artifact_id)

            if existing_entry is None:
                existing[artifact.artifact_id] = entry_dict
                added += 1
            elif existing_entry.get("artifact_hash") != artifact.artifact_hash:
                existing[artifact.artifact_id] = entry_dict
                updated += 1
            else:
                unchanged += 1

        # Sort by artifact_id for determinism
        sorted_entries = sorted(existing.values(), key=lambda e: e["artifact_id"])
        total = len(sorted_entries)

        ids_concat = "".join(e["artifact_id"] for e in sorted_entries)
        registry_hash = _sha256_text(ids_concat)

        registry_payload: dict[str, Any] = {
            "registry_hash": registry_hash,
            "total_count": total,
            "last_updated": _now_iso(),
            "entries": sorted_entries,
        }

        reg_path.parent.mkdir(parents=True, exist_ok=True)
        reg_path.write_text(
            json.dumps(registry_payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        logger.info(
            "Registry updated: added=%d updated=%d unchanged=%d total=%d path=%s",
            added,
            updated,
            unchanged,
            total,
            reg_path,
        )

        return RegistryUpdate(
            added=added,
            updated=updated,
            unchanged=unchanged,
            total=total,
            registry_hash=registry_hash,
            registry_path=str(reg_path),
        )

    def read_registry(self, registry_path: str) -> list[dict[str, Any]]:
        """
        Read and return all entries from knowledge_registry.json.

        Args:
            registry_path: Path to file or containing directory.

        Returns:
            List of entry dicts, empty list if file missing or corrupt.
        """
        p = Path(registry_path)
        if p.is_dir():
            p = p / self.DEFAULT_FILENAME
        if not p.exists():
            return []
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return data.get("entries", [])
        except Exception as exc:
            logger.warning("read_registry: error reading %s — %s", p, exc)
            return []
