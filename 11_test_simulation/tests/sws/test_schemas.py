"""Tests for SWS JSON schema validation against golden fixtures."""

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_DIR = REPO_ROOT / "03_core" / "sws" / "schemas"
GOLDEN_DIR = REPO_ROOT / "test_fixtures" / "sws_golden" / "expected_outputs"


def _load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _validate_required_keys(data: dict, required: list[str], name: str) -> None:
    missing = [k for k in required if k not in data]
    assert not missing, f"{name}: missing required keys: {missing}"


class TestSourceManifestSchema:
    def test_schema_file_exists(self):
        assert (SCHEMA_DIR / "source_manifest.schema.json").exists()

    def test_schema_is_valid_json(self):
        schema = _load_json(SCHEMA_DIR / "source_manifest.schema.json")
        assert "$schema" in schema
        assert schema["type"] == "object"

    def test_golden_fixture_matches_schema_required(self):
        schema = _load_json(SCHEMA_DIR / "source_manifest.schema.json")
        golden = _load_json(GOLDEN_DIR / "source_manifest.json")
        required = schema.get("required", [])
        _validate_required_keys(golden, required, "source_manifest")

    def test_golden_source_hash_format(self):
        golden = _load_json(GOLDEN_DIR / "source_manifest.json")
        h = golden["source_hash"]
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


class TestTranscriptMasterSchema:
    def test_schema_file_exists(self):
        assert (SCHEMA_DIR / "transcript_master.schema.json").exists()

    def test_golden_fixture_matches_schema_required(self):
        schema = _load_json(SCHEMA_DIR / "transcript_master.schema.json")
        golden = _load_json(GOLDEN_DIR / "transcript_master.json")
        required = schema.get("required", [])
        _validate_required_keys(golden, required, "transcript_master")

    def test_segments_have_required_fields(self):
        golden = _load_json(GOLDEN_DIR / "transcript_master.json")
        for seg in golden["segments"]:
            _validate_required_keys(
                seg,
                ["segment_id", "start_time", "end_time", "text", "confidence"],
                f"segment {seg.get('segment_id')}",
            )

    def test_full_text_concatenation(self):
        golden = _load_json(GOLDEN_DIR / "transcript_master.json")
        expected = " ".join(s["text"] for s in golden["segments"])
        assert golden["full_text"] == expected


class TestShotTimelineSchema:
    def test_schema_file_exists(self):
        assert (SCHEMA_DIR / "shot_timeline.schema.json").exists()

    def test_golden_fixture_matches_schema_required(self):
        schema = _load_json(SCHEMA_DIR / "shot_timeline.schema.json")
        golden = _load_json(GOLDEN_DIR / "shot_timeline.json")
        required = schema.get("required", [])
        _validate_required_keys(golden, required, "shot_timeline")

    def test_shot_count_consistency(self):
        golden = _load_json(GOLDEN_DIR / "shot_timeline.json")
        assert golden["total_shots"] == len(golden["shots"])

    def test_shots_cover_full_duration(self):
        golden = _load_json(GOLDEN_DIR / "shot_timeline.json")
        shots = golden["shots"]
        assert shots[0]["start_frame"] == 0
        assert shots[-1]["end_frame"] == 9000


class TestHookFingerprintSchema:
    def test_schema_file_exists(self):
        assert (SCHEMA_DIR / "hook_fingerprint.schema.json").exists()

    def test_golden_fixture_matches_schema_required(self):
        schema = _load_json(SCHEMA_DIR / "hook_fingerprint.schema.json")
        golden = _load_json(GOLDEN_DIR / "hook_fingerprint.json")
        required = schema.get("required", [])
        _validate_required_keys(golden, required, "hook_fingerprint")

    def test_empty_hooks_for_synthetic(self):
        golden = _load_json(GOLDEN_DIR / "hook_fingerprint.json")
        assert golden["hooks"] == []
