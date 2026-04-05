"""End-to-end tests for the full content pipeline.

Covers: full pipeline run (scan → extract → normalize → enrich → artifact),
KnowledgeArtifact integrity (artifact_id, artifact_hash), pipeline idempotency,
index persistence round-trip, and registry update.
"""

from __future__ import annotations

from pathlib import Path

from content_pipeline import (
    ContentExtractor,
    ContentIndexer,
    ContentRegistryUpdater,
    ContentTransformer,
    KnowledgeArtifact,
)


def _run_pipeline(source_dir: Path) -> list[KnowledgeArtifact]:
    """Helper: run full pipeline on source_dir, return artifacts."""
    extractor = ContentExtractor()
    transformer = ContentTransformer()
    sources = extractor.scan_sources([str(source_dir)])
    artifacts = []
    for sf in sources:
        extracted = extractor.extract_content(sf)
        normalized = transformer.normalize(extracted)
        enriched = transformer.enrich(normalized)
        artifact = transformer.to_knowledge_artifact(enriched)
        artifacts.append(artifact)
    return artifacts


# ---------------------------------------------------------------------------
# Test 1: Full pipeline produces at least one artifact per supported file
# ---------------------------------------------------------------------------


def test_pipeline_produces_artifacts_for_all_files(
    sample_source_dir: Path,
) -> None:
    """Pipeline should produce one artifact per supported source file."""
    extractor = ContentExtractor()
    sources = extractor.scan_sources([str(sample_source_dir)])
    artifacts = _run_pipeline(sample_source_dir)
    assert len(artifacts) == len(sources), f"Expected {len(sources)} artifacts, got {len(artifacts)}"
    for artifact in artifacts:
        assert isinstance(artifact, KnowledgeArtifact)
        assert artifact.artifact_id, "artifact_id must not be empty"
        assert artifact.artifact_hash, "artifact_hash must not be empty"


# ---------------------------------------------------------------------------
# Test 2: artifact_id is a 64-char hex SHA-256
# ---------------------------------------------------------------------------


def test_artifact_id_is_sha256_hex(sample_source_dir: Path) -> None:
    """artifact_id must be a 64-character lowercase hex string."""
    artifacts = _run_pipeline(sample_source_dir)
    assert artifacts, "Need at least one artifact"
    for a in artifacts:
        assert len(a.artifact_id) == 64
        assert all(c in "0123456789abcdef" for c in a.artifact_id), f"artifact_id is not hex: {a.artifact_id}"


# ---------------------------------------------------------------------------
# Test 3: Pipeline is idempotent (same files → same artifact_ids)
# ---------------------------------------------------------------------------


def test_pipeline_is_idempotent(sample_source_dir: Path) -> None:
    """Running the pipeline twice on the same files must produce identical artifact_ids."""
    run1 = _run_pipeline(sample_source_dir)
    run2 = _run_pipeline(sample_source_dir)
    ids1 = sorted(a.artifact_id for a in run1)
    ids2 = sorted(a.artifact_id for a in run2)
    assert ids1 == ids2, "Pipeline must be idempotent"


# ---------------------------------------------------------------------------
# Test 4: Index save/load round-trip preserves artifact count and hashes
# ---------------------------------------------------------------------------


def test_index_save_load_roundtrip(sample_source_dir: Path, tmp_dir: Path) -> None:
    """Saving and loading the index must produce identical artifact_ids."""
    artifacts = _run_pipeline(sample_source_dir)
    indexer = ContentIndexer()
    index = indexer.build_index(artifacts)
    indexer.save_index(index, str(tmp_dir))

    # Verify files exist
    assert (tmp_dir / "knowledge_index.json").exists()
    assert (tmp_dir / "policy_index.json").exists()
    assert (tmp_dir / "contract_index.json").exists()

    loaded = indexer.load_index(str(tmp_dir))
    assert loaded.total_count == index.total_count
    saved_ids = sorted(a.artifact_id for a in index.artifacts)
    loaded_ids = sorted(a.artifact_id for a in loaded.artifacts)
    assert saved_ids == loaded_ids, "Loaded artifact_ids must match saved"


# ---------------------------------------------------------------------------
# Test 5: Registry update records correct added/unchanged counts
# ---------------------------------------------------------------------------


def test_registry_update_counts(sample_source_dir: Path, tmp_dir: Path) -> None:
    """First registry update → all added. Second with same data → all unchanged."""
    artifacts = _run_pipeline(sample_source_dir)
    indexer = ContentIndexer()
    index = indexer.build_index(artifacts)
    updater = ContentRegistryUpdater()

    # First update: everything is new
    result1 = updater.update_registry(index, str(tmp_dir))
    assert result1.added == len(artifacts), f"Expected {len(artifacts)} added, got {result1.added}"
    assert result1.updated == 0
    assert result1.unchanged == 0

    # Second update with identical data: everything unchanged
    result2 = updater.update_registry(index, str(tmp_dir))
    assert result2.unchanged == len(artifacts)
    assert result2.added == 0
    assert result2.updated == 0
