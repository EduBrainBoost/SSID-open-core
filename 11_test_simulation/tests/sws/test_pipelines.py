"""Tests for SWS analysis pipelines — transcript, OCR, shot detect, hooks."""

import json
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "03_core"))

from sws.pipelines.transcript import (
    SyntheticTranscriptBackend,
    run_transcript_pipeline,
)
from sws.pipelines.ocr import SyntheticOcrBackend, run_ocr_pipeline
from sws.pipelines.shot_detect import (
    SyntheticShotDetectBackend,
    run_shot_detect_pipeline,
)
from sws.pipelines.hook_fingerprint import (
    detect_verbal_hooks,
    detect_visual_hooks,
    run_hook_fingerprint_pipeline,
)
from sws.pipelines.video_audio_analysis import (
    compute_quality_assessment,
    build_processing_metadata,
)


GOLDEN_DIR = REPO_ROOT / "test_fixtures" / "sws_golden" / "expected_outputs"


def _load_golden(name: str) -> dict:
    with open(GOLDEN_DIR / name, encoding="utf-8") as f:
        return json.load(f)


class TestTranscriptPipeline:
    def test_synthetic_produces_3_segments(self):
        with tempfile.NamedTemporaryFile(suffix=".mp4") as f:
            result = run_transcript_pipeline(Path(f.name))
        assert len(result["segments"]) == 3

    def test_output_matches_golden(self):
        golden = _load_golden("transcript_master.json")
        with tempfile.NamedTemporaryFile(suffix=".mp4") as f:
            result = run_transcript_pipeline(Path(f.name))
        assert result["transcript_id"] == golden["transcript_id"]
        assert result["language"] == golden["language"]
        assert len(result["segments"]) == len(golden["segments"])
        for actual, expected in zip(result["segments"], golden["segments"]):
            assert actual["text"] == expected["text"]
            assert actual["confidence"] == expected["confidence"]

    def test_full_text_is_concatenation(self):
        with tempfile.NamedTemporaryFile(suffix=".mp4") as f:
            result = run_transcript_pipeline(Path(f.name))
        expected = " ".join(s["text"] for s in result["segments"])
        assert result["full_text"] == expected


class TestOcrPipeline:
    def test_synthetic_produces_empty_layers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with tempfile.NamedTemporaryFile(suffix=".mp4", dir=tmpdir) as f:
                result = run_ocr_pipeline(
                    Path(f.name), Path(tmpdir), backend=SyntheticOcrBackend()
                )
        assert result["layers"] == []

    def test_output_matches_golden(self):
        golden = _load_golden("caption_layers.json")
        with tempfile.TemporaryDirectory() as tmpdir:
            with tempfile.NamedTemporaryFile(suffix=".mp4", dir=tmpdir) as f:
                result = run_ocr_pipeline(
                    Path(f.name), Path(tmpdir), backend=SyntheticOcrBackend()
                )
        assert result == golden


class TestShotDetectPipeline:
    def test_synthetic_produces_3_shots(self):
        with tempfile.NamedTemporaryFile(suffix=".mp4") as f:
            result = run_shot_detect_pipeline(Path(f.name))
        assert result["total_shots"] == 3

    def test_output_matches_golden(self):
        golden = _load_golden("shot_timeline.json")
        with tempfile.NamedTemporaryFile(suffix=".mp4") as f:
            result = run_shot_detect_pipeline(Path(f.name))
        assert result["total_shots"] == golden["total_shots"]
        for actual, expected in zip(result["shots"], golden["shots"]):
            assert actual["shot_id"] == expected["shot_id"]
            assert actual["start_frame"] == expected["start_frame"]
            assert actual["end_frame"] == expected["end_frame"]
            assert actual["scene_type"] == expected["scene_type"]
            assert actual["confidence"] == expected["confidence"]

    def test_shots_are_contiguous(self):
        with tempfile.NamedTemporaryFile(suffix=".mp4") as f:
            result = run_shot_detect_pipeline(Path(f.name))
        shots = result["shots"]
        for i in range(1, len(shots)):
            assert shots[i]["start_frame"] == shots[i - 1]["end_frame"]


class TestHookFingerprintPipeline:
    def test_no_hooks_for_synthetic(self):
        golden_transcript = _load_golden("transcript_master.json")
        golden_shots = _load_golden("shot_timeline.json")
        result = run_hook_fingerprint_pipeline(
            golden_transcript, golden_shots, 300
        )
        assert result["hooks"] == []
        assert "note" in result

    def test_verbal_hook_detection(self):
        segments = [
            {"segment_id": 1, "start_time": 0, "end_time": 10, "text": "Click the subscribe button below!", "confidence": 0.9},
        ]
        hooks = detect_verbal_hooks(segments)
        assert len(hooks) >= 1
        types = {h.hook_type for h in hooks}
        assert "cta_verbal" in types

    def test_visual_hook_fast_opening(self):
        shots = [
            {"shot_id": "shot_001", "start_frame": 0, "end_frame": 90, "duration_seconds": 3.0, "scene_type": "opening_static", "confidence": 0.9},
            {"shot_id": "shot_002", "start_frame": 90, "end_frame": 9000, "duration_seconds": 297.0, "scene_type": "dialogue", "confidence": 0.85},
        ]
        hooks = detect_visual_hooks(shots, 300)
        assert len(hooks) >= 1
        assert hooks[0].hook_type == "opening_hook"


class TestVideoAudioAnalysis:
    def test_quality_assessment_structure(self):
        transcript = _load_golden("transcript_master.json")
        shots = _load_golden("shot_timeline.json")
        media = _load_golden("media_technical.json")
        result = compute_quality_assessment(transcript, shots, media)
        assert "overall_score" in result
        assert "components" in result
        assert "warnings" in result
        assert 0 <= result["overall_score"] <= 1

    def test_quality_matches_golden(self):
        transcript = _load_golden("transcript_master.json")
        shots = _load_golden("shot_timeline.json")
        media = _load_golden("media_technical.json")
        golden = _load_golden("quality_assessment.json")
        result = compute_quality_assessment(transcript, shots, media)
        assert abs(result["overall_score"] - golden["overall_score"]) <= 0.02
        assert result["components"]["video_clarity"] == golden["components"]["video_clarity"]

    def test_processing_metadata_structure(self):
        result = build_processing_metadata(
            ["frame_extraction", "shot_detection"], 5.0
        )
        assert result["analyzer_version"] == "sws_analyzer_v1.0"
        assert result["processing_duration_seconds"] == 5.0
        assert len(result["stages_completed"]) == 2
