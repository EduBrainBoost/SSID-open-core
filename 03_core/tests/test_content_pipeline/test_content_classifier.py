"""Tests for ContentClassifier.

Covers: category assignment for governance/policy/contract/technical/knowledge,
path-based signals, confidence scores in [0,1], evidence hash determinism,
and primary category selection.
"""

from __future__ import annotations

import pytest
from content_pipeline.content_classifier import (
    CATEGORIES,
    Classification,
    ContentClassifier,
)
from content_pipeline.content_extractor import ExtractedContent


@pytest.fixture()
def classifier() -> ContentClassifier:
    return ContentClassifier()


def _make_content(
    title: str = "",
    body: str = "",
    source_path: str = "/data/docs/sample.md",
    content_type: str = "markdown",
) -> ExtractedContent:
    import hashlib

    return ExtractedContent(
        title=title,
        body=body,
        metadata={},
        content_type=content_type,
        source_path=source_path,
        hash=hashlib.sha256(body.encode()).hexdigest(),
    )


# ---------------------------------------------------------------------------
# Test 1: Policy content classifies as 'policy' primary category
# ---------------------------------------------------------------------------


def test_classify_policy_content(classifier: ContentClassifier) -> None:
    """Content with 'policy', 'allow', 'deny' keywords + .rego type → policy primary."""
    content = _make_content(
        title="Access Policy",
        body="default allow = false\ndeny if input.role != 'admin'\npermission required",
        source_path="/ssid/policies/access.rego",
        content_type="policy",
    )
    result = classifier.classify(content)
    assert isinstance(result, Classification)
    assert result.primary_category == "policy", f"Expected 'policy', got '{result.primary_category}'"


# ---------------------------------------------------------------------------
# Test 2: Contract content classifies as 'contract' primary category
# ---------------------------------------------------------------------------


def test_classify_contract_content(classifier: ContentClassifier) -> None:
    """Content under contracts/ path with contract keywords → contract primary."""
    content = _make_content(
        title="Service Level Agreement",
        body="This agreement between the parties defines SLA obligations and liability.",
        source_path="/ssid/contracts/sla.md",
    )
    result = classifier.classify(content)
    assert result.primary_category == "contract", f"Expected 'contract', got '{result.primary_category}'"


# ---------------------------------------------------------------------------
# Test 3: All confidence scores are clamped to [0, 1]
# ---------------------------------------------------------------------------


def test_all_scores_clamped_to_unit_interval(classifier: ContentClassifier) -> None:
    """Every CategoryScore.score must be in [0.0, 1.0]."""
    content = _make_content(
        title="Everything",
        body=(
            "architecture governance policy contract compliance technical "
            "knowledge API audit GDPR SLA allow deny decision"
        ),
        source_path="/mixed/doc.md",
    )
    result = classifier.classify(content)
    for cs in result.all_scores:
        assert 0.0 <= cs.score <= 1.0, f"Score out of range for {cs.category}: {cs.score}"


# ---------------------------------------------------------------------------
# Test 4: Classification is deterministic (same input → same hashes)
# ---------------------------------------------------------------------------


def test_classification_deterministic(classifier: ContentClassifier) -> None:
    """Classifying the same content twice must produce identical hashes."""
    content = _make_content(
        title="Architecture Decision",
        body="ADR-001: Use modular architecture with isolated engines.",
        source_path="/docs/adr/001.md",
    )
    r1 = classifier.classify(content)
    r2 = classifier.classify(content)
    assert r1.input_hash == r2.input_hash
    assert r1.evidence_hash == r2.evidence_hash
    assert r1.primary_category == r2.primary_category


# ---------------------------------------------------------------------------
# Test 5: all_scores contains all vocabulary categories
# ---------------------------------------------------------------------------


def test_all_categories_present_in_scores(classifier: ContentClassifier) -> None:
    """all_scores must contain exactly one entry per category in CATEGORIES."""
    content = _make_content(title="Simple doc", body="A simple knowledge document.")
    result = classifier.classify(content)
    scored_cats = {cs.category for cs in result.all_scores}
    assert scored_cats == set(CATEGORIES), f"Missing categories: {set(CATEGORIES) - scored_cats}"
