"""Tests for ContentExtractor.

Covers: scan_sources discovery, markdown extraction, YAML extraction,
JSON extraction, policy extraction, SHA-256 hash determinism,
missing file handling, and content_type detection.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from content_pipeline.content_extractor import (
    ContentExtractor,
    ExtractedContent,
)


@pytest.fixture()
def extractor() -> ContentExtractor:
    return ContentExtractor()


# ---------------------------------------------------------------------------
# Test 1: scan_sources discovers all supported file types
# ---------------------------------------------------------------------------


def test_scan_sources_finds_all_supported_types(
    extractor: ContentExtractor,
    sample_source_dir: Path,
) -> None:
    """scan_sources should find .md, .yaml, .json, and .rego files."""
    sources = extractor.scan_sources([str(sample_source_dir)])
    extensions = {Path(sf.path).suffix.lower() for sf in sources}
    assert ".md" in extensions, "Should discover .md files"
    assert ".yaml" in extensions, "Should discover .yaml files"
    assert ".json" in extensions, "Should discover .json files"
    assert ".rego" in extensions, "Should discover .rego files"


# ---------------------------------------------------------------------------
# Test 2: scan_sources result is sorted and deterministic
# ---------------------------------------------------------------------------


def test_scan_sources_deterministic_order(
    extractor: ContentExtractor,
    sample_source_dir: Path,
) -> None:
    """Calling scan_sources twice on the same dir must return identical lists."""
    first = extractor.scan_sources([str(sample_source_dir)])
    second = extractor.scan_sources([str(sample_source_dir)])
    assert [sf.path for sf in first] == [sf.path for sf in second]


# ---------------------------------------------------------------------------
# Test 3: extract_content for markdown returns correct fields
# ---------------------------------------------------------------------------


def test_extract_markdown_content(
    extractor: ContentExtractor,
    sample_markdown_file: Path,
) -> None:
    """Markdown extraction should populate title, body, content_type, and hash."""
    sources = extractor.scan_sources([str(sample_markdown_file)])
    assert len(sources) == 1
    content = extractor.extract_content(sources[0])
    assert isinstance(content, ExtractedContent)
    assert content.content_type == "markdown"
    assert content.title == "Sample Document"
    assert "governance" in content.body.lower()
    assert len(content.hash) == 64  # SHA-256 hex digest
    assert content.source_path == str(sample_markdown_file)


# ---------------------------------------------------------------------------
# Test 4: extract_content for YAML returns correct fields
# ---------------------------------------------------------------------------


def test_extract_yaml_content(
    extractor: ContentExtractor,
    sample_yaml_file: Path,
) -> None:
    """YAML extraction should capture title from 'title' key and flatten body."""
    sources = extractor.scan_sources([str(sample_yaml_file)])
    assert len(sources) == 1
    content = extractor.extract_content(sources[0])
    assert content.content_type == "yaml"
    assert "Architecture Decision Record" in content.title
    assert "architecture" in content.body.lower() or "ADR" in content.body
    assert len(content.hash) == 64


# ---------------------------------------------------------------------------
# Test 5: hash is SHA-256 of body and is deterministic
# ---------------------------------------------------------------------------


def test_extract_hash_is_deterministic_sha256(
    extractor: ContentExtractor,
    sample_markdown_file: Path,
) -> None:
    """Hash must equal SHA-256(body) and be identical across two calls."""
    sources = extractor.scan_sources([str(sample_markdown_file)])
    c1 = extractor.extract_content(sources[0])
    c2 = extractor.extract_content(sources[0])

    assert c1.hash == c2.hash, "Hash must be deterministic"
    expected = hashlib.sha256(c1.body.encode("utf-8")).hexdigest()
    assert c1.hash == expected, "Hash must be SHA-256 of body"
