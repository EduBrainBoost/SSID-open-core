"""Tests for SWS ingest adapter and media normalizer."""

import json
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "03_core"))

from sws.adapters.ingest import (
    IngestResult,
    RightsToken,
    RightsError,
    IngestError,
    ingest_file,
    validate_rights,
    build_source_manifest,
)
from sws.adapters.media_normalize import (
    MediaProbe,
    build_media_technical,
    build_audio_map,
)


def _make_rights_token(**kwargs) -> RightsToken:
    defaults = {
        "token_id": "test_token_001",
        "issuer": "test_issuer",
        "granted_at": "2026-04-17T00:00:00Z",
    }
    defaults.update(kwargs)
    return RightsToken(**defaults)


class TestRightsValidation:
    def test_valid_token_passes(self):
        token = _make_rights_token()
        validate_rights(token)  # should not raise

    def test_none_token_raises(self):
        with pytest.raises(RightsError, match="No rights token"):
            validate_rights(None)

    def test_expired_token_raises(self):
        token = _make_rights_token(expires_at="2020-01-01T00:00:00Z")
        with pytest.raises(RightsError, match="expired"):
            validate_rights(token)

    def test_missing_permission_raises(self):
        token = _make_rights_token(permissions=["read_only"])
        with pytest.raises(RightsError, match="lacks"):
            validate_rights(token)


class TestFileIngest:
    def test_ingest_existing_file(self):
        token = _make_rights_token()
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "test_video.mp4"
            source.write_bytes(b"fake video content for testing")
            staging = Path(tmpdir) / "staging"

            result = ingest_file(source, staging, token)

            assert result.source_id.startswith("src_")
            assert result.local_path.exists()
            assert result.file_size_bytes > 0
            assert len(result.source_hash) == 64
            assert result.origin == "file"

    def test_ingest_nonexistent_file_raises(self):
        token = _make_rights_token()
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(IngestError, match="does not exist"):
                ingest_file("/nonexistent/path.mp4", tmpdir, token)

    def test_ingest_without_token_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "test.mp4"
            source.write_bytes(b"data")
            with pytest.raises(RightsError):
                ingest_file(source, tmpdir, None)


class TestSourceManifestBuilder:
    def test_builds_correct_structure(self):
        result = IngestResult(
            source_id="src_test",
            local_path=Path("/tmp/test.mp4"),
            source_hash="a" * 64,
            file_size_bytes=1000,
            ingested_at="2026-04-17T00:00:00Z",
            origin="file",
            original_reference="/tmp/test.mp4",
        )
        manifest = build_source_manifest(
            result,
            width=1920, height=1080, frame_rate=30.0,
            duration_seconds=300, codec_video="h264",
            codec_audio="aac", sample_rate=44100, channels=2,
        )
        assert manifest["source_id"] == "src_test"
        assert manifest["width"] == 1920
        assert manifest["source_hash"] == "a" * 64


class TestMediaNormalize:
    def _make_probe(self, **overrides) -> MediaProbe:
        defaults = dict(
            width=1920, height=1080, aspect_ratio="16:9",
            duration_seconds=300, frame_rate=30.0, total_frames=9000,
            video_codec="h264", video_profile="high",
            audio_codec="aac", audio_sample_rate=44100, audio_channels=1,
            bitrate_video_kbps=2500, bitrate_audio_kbps=128, pix_fmt="yuv420p",
        )
        defaults.update(overrides)
        return MediaProbe(**defaults)

    def test_media_technical_structure(self):
        probe = self._make_probe()
        result = build_media_technical(probe)
        assert result["resolution"]["width"] == 1920
        assert result["temporal"]["total_frames"] == 9000
        assert result["codec"]["video_codec"] == "h264"

    def test_audio_map_mono_to_stereo(self):
        probe = self._make_probe(audio_channels=1)
        result = build_audio_map(probe, target_channels=2)
        assert result["source_channels"] == 1
        assert result["output_channels"] == 2
        assert result["channel_map"]["channel_0"]["type"] == "mono_to_stereo"

    def test_audio_map_passthrough(self):
        probe = self._make_probe(audio_channels=2)
        result = build_audio_map(probe, target_channels=2)
        assert result["source_channels"] == 2
        assert result["channel_map"]["channel_0"]["type"] == "passthrough"

    def test_audio_map_no_audio(self):
        probe = self._make_probe(audio_channels=0)
        result = build_audio_map(probe)
        assert result["source_channels"] == 0
        assert result["channel_map"] == {}
