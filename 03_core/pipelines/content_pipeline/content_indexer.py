"""content_indexer.py — Build, search, persist, and load a KnowledgeIndex.

Stores three index files on disk:
  - knowledge_index.json   (all artifacts)
  - policy_index.json      (category == "policy")
  - contract_index.json    (category == "contract")

Full-text search with optional tag/category filtering.
Deterministic output: artifact ordering is by artifact_id (lexicographic).
No PII; all content hashes are SHA-256.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .content_transformer import KnowledgeArtifact

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class SearchResult:
    """A single search hit with relevance score."""

    artifact_id: str
    title: str
    summary: str
    source_path: str
    content_type: str
    categories: list[str]
    tags: list[str]
    score: float          # relevance score (0.0 – 1.0)
    hash: str


@dataclass
class KnowledgeIndex:
    """Container for all indexed knowledge artifacts."""

    artifacts: list[KnowledgeArtifact]
    total_count: int
    index_hash: str       # SHA-256 of sorted artifact_ids (for integrity)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _artifact_to_dict(artifact: KnowledgeArtifact) -> dict[str, Any]:
    """Serialise a KnowledgeArtifact to a JSON-safe dict."""
    return {
        "artifact_id": artifact.artifact_id,
        "title": artifact.title,
        "body": artifact.body,
        "summary": artifact.summary,
        "metadata": artifact.metadata,
        "content_type": artifact.content_type,
        "source_path": artifact.source_path,
        "hash": artifact.hash,
        "tags": list(artifact.tags),
        "categories": list(artifact.categories),
        "cross_references": list(artifact.cross_references),
        "artifact_hash": artifact.artifact_hash,
    }


def _dict_to_artifact(d: dict[str, Any]) -> KnowledgeArtifact:
    """Deserialise a dict back into a KnowledgeArtifact."""
    return KnowledgeArtifact(
        artifact_id=d["artifact_id"],
        title=d["title"],
        body=d.get("body", ""),
        summary=d.get("summary", ""),
        metadata=d.get("metadata", {}),
        content_type=d["content_type"],
        source_path=d["source_path"],
        hash=d["hash"],
        tags=tuple(d.get("tags", [])),
        categories=tuple(d.get("categories", [])),
        cross_references=tuple(d.get("cross_references", [])),
        artifact_hash=d.get("artifact_hash", ""),
    )


def _score_artifact(artifact: KnowledgeArtifact, query_tokens: list[str]) -> float:
    """Simple TF-style relevance score for full-text search."""
    if not query_tokens:
        return 1.0
    searchable = " ".join([
        artifact.title,
        artifact.summary,
        " ".join(artifact.tags),
        " ".join(artifact.categories),
        artifact.source_path,
    ]).lower()
    hits = sum(1 for token in query_tokens if token in searchable)
    # Title hits count double
    title_hits = sum(2 for token in query_tokens if token in artifact.title.lower())
    raw = (hits + title_hits) / (len(query_tokens) * 3 or 1)
    return round(min(1.0, raw), 4)


def _tokenise(query: str) -> list[str]:
    return [t.lower() for t in re.split(r"\s+", query.strip()) if t]


# ---------------------------------------------------------------------------
# ContentIndexer
# ---------------------------------------------------------------------------


class ContentIndexer:
    """
    Builds and queries a KnowledgeIndex from KnowledgeArtifact records.

    Index files:
        <base_dir>/knowledge_index.json   — all artifacts
        <base_dir>/policy_index.json      — policy-category artifacts
        <base_dir>/contract_index.json    — contract-category artifacts

    All methods are deterministic given identical input artifacts.
    """

    def build_index(self, artifacts: list[KnowledgeArtifact]) -> KnowledgeIndex:
        """
        Build a KnowledgeIndex from a list of KnowledgeArtifacts.

        Artifacts are sorted by artifact_id for determinism.
        index_hash = SHA-256 of concatenated sorted artifact_ids.

        Args:
            artifacts: List of KnowledgeArtifact records.

        Returns:
            KnowledgeIndex with total_count and index_hash.
        """
        sorted_artifacts = sorted(artifacts, key=lambda a: a.artifact_id)
        ids_concat = "".join(a.artifact_id for a in sorted_artifacts)
        index_hash = _sha256_text(ids_concat)
        return KnowledgeIndex(
            artifacts=sorted_artifacts,
            total_count=len(sorted_artifacts),
            index_hash=index_hash,
        )

    def search(
        self,
        query: str,
        filters: dict[str, Any],
        index: KnowledgeIndex | None = None,
        index_path: str | None = None,
    ) -> list[SearchResult]:
        """
        Full-text search over the index with optional tag/category filtering.

        Args:
            query: Search string (space-separated tokens, case-insensitive).
            filters: Optional dict with keys:
                     - "category": str — filter by category
                     - "tag": str      — filter by tag
                     - "content_type": str
                     - "limit": int    (default 50)
            index: Pre-built KnowledgeIndex (used if provided).
            index_path: Path to knowledge_index.json (used if index is None).

        Returns:
            List of SearchResult sorted by score descending.
        """
        if index is None:
            if index_path is None:
                return []
            index = self.load_index(index_path)

        tokens = _tokenise(query)
        limit: int = int(filters.get("limit", 50))
        cat_filter: str | None = filters.get("category")
        tag_filter: str | None = filters.get("tag")
        type_filter: str | None = filters.get("content_type")

        results: list[SearchResult] = []
        for artifact in index.artifacts:
            # Apply filters
            if cat_filter and cat_filter not in artifact.categories:
                continue
            if tag_filter and tag_filter not in artifact.tags:
                continue
            if type_filter and artifact.content_type != type_filter:
                continue

            score = _score_artifact(artifact, tokens)
            if score == 0.0 and tokens:
                continue

            results.append(
                SearchResult(
                    artifact_id=artifact.artifact_id,
                    title=artifact.title,
                    summary=artifact.summary,
                    source_path=artifact.source_path,
                    content_type=artifact.content_type,
                    categories=list(artifact.categories),
                    tags=list(artifact.tags),
                    score=score,
                    hash=artifact.hash,
                )
            )

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    def save_index(self, index: KnowledgeIndex, base_path: str) -> None:
        """
        Persist the index to three JSON files under base_path.

        Files written:
            knowledge_index.json   — all artifacts
            policy_index.json      — policy-only subset
            contract_index.json    — contract-only subset

        Args:
            index: KnowledgeIndex to persist.
            base_path: Directory path (created if missing).
        """
        out_dir = Path(base_path)
        out_dir.mkdir(parents=True, exist_ok=True)

        def _write(filename: str, artifacts: list[KnowledgeArtifact]) -> None:
            payload = {
                "total_count": len(artifacts),
                "index_hash": _sha256_text("".join(a.artifact_id for a in artifacts)),
                "artifacts": [_artifact_to_dict(a) for a in artifacts],
            }
            (out_dir / filename).write_text(
                json.dumps(payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            logger.debug("Wrote %s (%d artifacts)", filename, len(artifacts))

        _write("knowledge_index.json", index.artifacts)

        policy_artifacts = [a for a in index.artifacts if "policy" in a.categories]
        _write("policy_index.json", policy_artifacts)

        contract_artifacts = [a for a in index.artifacts if "contract" in a.categories]
        _write("contract_index.json", contract_artifacts)

        logger.info(
            "Index saved to %s: total=%d policy=%d contract=%d",
            base_path,
            index.total_count,
            len(policy_artifacts),
            len(contract_artifacts),
        )

    def load_index(self, path: str) -> KnowledgeIndex:
        """
        Load a KnowledgeIndex from a knowledge_index.json file.

        Args:
            path: Full path to the JSON file (or directory containing it).

        Returns:
            KnowledgeIndex, or empty index if file is missing/corrupt.
        """
        p = Path(path)
        if p.is_dir():
            p = p / "knowledge_index.json"
        if not p.exists():
            logger.debug("load_index: file not found: %s", p)
            return KnowledgeIndex(artifacts=[], total_count=0, index_hash="")
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            artifacts = [_dict_to_artifact(d) for d in data.get("artifacts", [])]
            ids_concat = "".join(a.artifact_id for a in artifacts)
            return KnowledgeIndex(
                artifacts=artifacts,
                total_count=len(artifacts),
                index_hash=_sha256_text(ids_concat),
            )
        except Exception as exc:
            logger.warning("load_index: error reading %s — %s", p, exc)
            return KnowledgeIndex(artifacts=[], total_count=0, index_hash="")

    def load_policy_index(self, base_path: str) -> KnowledgeIndex:
        """Load the policy-specific sub-index."""
        p = Path(base_path)
        if p.is_dir():
            p = p / "policy_index.json"
        return self._load_sub_index(p)

    def load_contract_index(self, base_path: str) -> KnowledgeIndex:
        """Load the contract-specific sub-index."""
        p = Path(base_path)
        if p.is_dir():
            p = p / "contract_index.json"
        return self._load_sub_index(p)

    def _load_sub_index(self, path: Path) -> KnowledgeIndex:
        if not path.exists():
            return KnowledgeIndex(artifacts=[], total_count=0, index_hash="")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            artifacts = [_dict_to_artifact(d) for d in data.get("artifacts", [])]
            return KnowledgeIndex(
                artifacts=artifacts,
                total_count=len(artifacts),
                index_hash=data.get("index_hash", ""),
            )
        except Exception as exc:
            logger.warning("_load_sub_index: error reading %s — %s", path, exc)
            return KnowledgeIndex(artifacts=[], total_count=0, index_hash="")
