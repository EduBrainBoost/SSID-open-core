"""Tests for ContentIndexer search functionality.

Covers: full-text search returns relevant results, category filter,
tag filter, empty query returns all results, no match returns empty list,
and score ordering.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from content_pipeline.content_indexer import ContentIndexer, KnowledgeIndex
from content_pipeline.content_transformer import KnowledgeArtifact


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_artifact(
    title: str,
    body: str,
    categories: tuple[str, ...],
    tags: tuple[str, ...],
    source_path: str = "/docs/sample.md",
    content_type: str = "markdown",
) -> KnowledgeArtifact:
    body_hash = hashlib.sha256(body.encode()).hexdigest()
    artifact_id = hashlib.sha256((source_path + body_hash).encode()).hexdigest()
    artifact_hash = hashlib.sha256(artifact_id.encode()).hexdigest()
    return KnowledgeArtifact(
        artifact_id=artifact_id,
        title=title,
        body=body,
        summary=body[:400],
        metadata={},
        content_type=content_type,
        source_path=source_path,
        hash=body_hash,
        tags=tags,
        categories=categories,
        cross_references=(),
        artifact_hash=artifact_hash,
    )


@pytest.fixture()
def populated_index() -> KnowledgeIndex:
    """A KnowledgeIndex with three distinct artifacts."""
    indexer = ContentIndexer()
    artifacts = [
        _make_artifact(
            title="Governance Policy",
            body="This governance policy enforces compliance rules for all teams.",
            categories=("governance", "policy"),
            tags=("policy", "governance"),
            source_path="/ssid/policies/governance.md",
        ),
        _make_artifact(
            title="Architecture Decision Record",
            body="ADR-001 describes the modular architecture with isolated engines.",
            categories=("architecture",),
            tags=("architecture", "adr"),
            source_path="/ssid/docs/adr/001.md",
        ),
        _make_artifact(
            title="Service Level Agreement",
            body="SLA contract between SSID and external partner with defined obligations.",
            categories=("contract",),
            tags=("contract", "sla"),
            source_path="/ssid/contracts/sla.md",
        ),
    ]
    return indexer.build_index(artifacts)


@pytest.fixture()
def indexer() -> ContentIndexer:
    return ContentIndexer()


# ---------------------------------------------------------------------------
# Test 1: Full-text search returns the most relevant result first
# ---------------------------------------------------------------------------


def test_search_returns_relevant_result_first(
    indexer: ContentIndexer,
    populated_index: KnowledgeIndex,
) -> None:
    """Searching for 'ADR' should rank the architecture ADR artifact highest."""
    results = indexer.search("ADR", {}, index=populated_index)
    assert results, "Expected at least one search result"
    assert "Architecture" in results[0].title, (
        f"Top result should be the ADR, got: {results[0].title}"
    )


# ---------------------------------------------------------------------------
# Test 2: Category filter restricts results to matching category
# ---------------------------------------------------------------------------


def test_search_category_filter(
    indexer: ContentIndexer,
    populated_index: KnowledgeIndex,
) -> None:
    """A category='contract' filter must return only contract artifacts."""
    results = indexer.search("", {"category": "contract"}, index=populated_index)
    assert len(results) == 1, f"Expected 1 contract result, got {len(results)}"
    assert "contract" in results[0].categories


# ---------------------------------------------------------------------------
# Test 3: Tag filter restricts results to matching tag
# ---------------------------------------------------------------------------


def test_search_tag_filter(
    indexer: ContentIndexer,
    populated_index: KnowledgeIndex,
) -> None:
    """A tag='architecture' filter must return only architecture-tagged artifacts."""
    results = indexer.search("", {"tag": "architecture"}, index=populated_index)
    assert len(results) == 1
    assert "architecture" in results[0].tags


# ---------------------------------------------------------------------------
# Test 4: Empty query with no filters returns all artifacts
# ---------------------------------------------------------------------------


def test_search_empty_query_returns_all(
    indexer: ContentIndexer,
    populated_index: KnowledgeIndex,
) -> None:
    """An empty query with no filters should return all indexed artifacts."""
    results = indexer.search("", {}, index=populated_index)
    assert len(results) == populated_index.total_count, (
        f"Expected {populated_index.total_count} results, got {len(results)}"
    )


# ---------------------------------------------------------------------------
# Test 5: No-match query returns empty list, not an error
# ---------------------------------------------------------------------------


def test_search_no_match_returns_empty(
    indexer: ContentIndexer,
    populated_index: KnowledgeIndex,
) -> None:
    """A query with no matching tokens must return an empty list."""
    results = indexer.search("xyzzy_nonexistent_token_12345", {}, index=populated_index)
    assert results == [], f"Expected [], got {results}"
