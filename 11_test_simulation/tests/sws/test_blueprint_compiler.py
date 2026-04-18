"""Tests for SWS blueprint compiler integration."""

import json
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "03_core"))

from sws.adapters.ingest import RightsToken
from sws.core.blueprint_compiler import (
    BlueprintConfig,
    BlueprintCompileError,
    compile_blueprint,
    compile_blueprint_to_file,
)

GOLDEN_DIR = REPO_ROOT / "test_fixtures" / "sws_golden" / "expected_outputs"


def _make_token() -> RightsToken:
    return RightsToken(
        token_id="test_token_001",
        issuer="test_issuer",
        granted_at="2026-04-17T00:00:00Z",
    )


class TestBlueprintCompiler:
    def test_compile_produces_11_artifacts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "test_video.mp4"
            source.write_bytes(b"synthetic test content for blueprint")

            config = BlueprintConfig(
                source=str(source),
                source_type="file",
                staging_dir=str(Path(tmpdir) / "staging"),
                work_dir=str(Path(tmpdir) / "work"),
                rights_token=_make_token(),
            )
            result = compile_blueprint(config)

        assert len(result.artifacts) == 11
        expected_keys = {
            "source_manifest", "media_technical", "audio_map",
            "shot_timeline", "transcript_master", "caption_layers",
            "hook_fingerprint", "quality_assessment", "processing_metadata",
            "archive_metadata", "validation_report",
        }
        assert set(result.artifacts.keys()) == expected_keys

    def test_blueprint_has_version_and_hashes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "test_video.mp4"
            source.write_bytes(b"synthetic test content for blueprint")

            config = BlueprintConfig(
                source=str(source),
                staging_dir=str(Path(tmpdir) / "staging"),
                work_dir=str(Path(tmpdir) / "work"),
                rights_token=_make_token(),
            )
            result = compile_blueprint(config)

        bp = result.blueprint
        assert bp["blueprint_version"] == "1.0"
        assert bp["artifact_count"] == 11
        assert len(bp["artifact_hashes"]) == 11
        for name, h in bp["artifact_hashes"].items():
            assert len(h) == 64, f"Hash for {name} is not SHA-256"

    def test_validation_report_passes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "test_video.mp4"
            source.write_bytes(b"synthetic test content for blueprint")

            config = BlueprintConfig(
                source=str(source),
                staging_dir=str(Path(tmpdir) / "staging"),
                work_dir=str(Path(tmpdir) / "work"),
                rights_token=_make_token(),
            )
            result = compile_blueprint(config)

        vr = result.validation
        assert vr["status"] == "PASS"
        assert vr["checks_passed"] == vr["checks_total"]

    def test_compile_to_file_creates_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "test_video.mp4"
            source.write_bytes(b"synthetic test content for blueprint")
            output = Path(tmpdir) / "output" / "rebuild_blueprint.json"

            config = BlueprintConfig(
                source=str(source),
                staging_dir=str(Path(tmpdir) / "staging"),
                work_dir=str(Path(tmpdir) / "work"),
                rights_token=_make_token(),
            )
            result = compile_blueprint_to_file(config, output)

            assert result.output_path.exists()
            with open(result.output_path) as f:
                data = json.load(f)
            assert data["blueprint_version"] == "1.0"
            assert data["artifact_count"] == 11

    def test_compile_without_rights_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "test_video.mp4"
            source.write_bytes(b"data")

            config = BlueprintConfig(
                source=str(source),
                staging_dir=str(Path(tmpdir) / "staging"),
                work_dir=str(Path(tmpdir) / "work"),
                rights_token=None,
            )
            with pytest.raises(BlueprintCompileError, match="Ingest failed"):
                compile_blueprint(config)

    def test_transcript_matches_golden_structure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "test_video.mp4"
            source.write_bytes(b"synthetic test content")

            config = BlueprintConfig(
                source=str(source),
                staging_dir=str(Path(tmpdir) / "staging"),
                work_dir=str(Path(tmpdir) / "work"),
                rights_token=_make_token(),
            )
            result = compile_blueprint(config)

        golden = json.loads((GOLDEN_DIR / "transcript_master.json").read_text())
        actual = result.artifacts["transcript_master"]
        assert actual["language"] == golden["language"]
        assert len(actual["segments"]) == len(golden["segments"])

    def test_shot_timeline_matches_golden_structure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "test_video.mp4"
            source.write_bytes(b"synthetic test content")

            config = BlueprintConfig(
                source=str(source),
                staging_dir=str(Path(tmpdir) / "staging"),
                work_dir=str(Path(tmpdir) / "work"),
                rights_token=_make_token(),
            )
            result = compile_blueprint(config)

        golden = json.loads((GOLDEN_DIR / "shot_timeline.json").read_text())
        actual = result.artifacts["shot_timeline"]
        assert actual["total_shots"] == golden["total_shots"]
