"""
Video/audio feature analysis for SWS Analyze Spine.

Produces quality_assessment.json and processing_metadata.json artifacts.
Aggregates quality signals from all pipeline stages.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional


def compute_quality_assessment(
    transcript_master: dict,
    shot_timeline: dict,
    media_probe: Optional[dict] = None,
) -> dict:
    """
    Compute overall quality score from pipeline outputs.

    Components:
    - video_clarity: derived from resolution and codec quality
    - audio_quality: derived from transcript confidence
    - shot_detection_confidence: mean shot confidence
    - transcript_confidence: mean segment confidence

    Args:
        transcript_master: transcript_master.json dict.
        shot_timeline: shot_timeline.json dict.
        media_probe: media_technical.json dict (optional).

    Returns:
        quality_assessment.json-conformant dict.
    """
    # Transcript confidence
    segments = transcript_master.get("segments", [])
    if segments:
        transcript_conf = sum(s.get("confidence", 0) for s in segments) / len(segments)
    else:
        transcript_conf = 0.0

    # Shot detection confidence
    shots = shot_timeline.get("shots", [])
    if shots:
        shot_conf = sum(s.get("confidence", 0) for s in shots) / len(shots)
    else:
        shot_conf = 0.0

    # Video clarity from resolution
    if media_probe:
        res = media_probe.get("resolution", {})
        w = res.get("width", 0)
        h = res.get("height", 0)
        if w >= 1920 and h >= 1080:
            video_clarity = 0.92
        elif w >= 1280 and h >= 720:
            video_clarity = 0.80
        elif w >= 640 and h >= 480:
            video_clarity = 0.65
        else:
            video_clarity = 0.50
    else:
        video_clarity = 0.85

    # Audio quality from transcript confidence
    audio_quality = min(transcript_conf * 0.95, 1.0) if transcript_conf > 0 else 0.5

    overall = round(
        (video_clarity + audio_quality + shot_conf + transcript_conf) / 4, 2
    )

    warnings = []
    if transcript_conf < 0.5:
        warnings.append("Low transcript confidence — audio quality may be poor")
    if shot_conf < 0.5:
        warnings.append("Low shot detection confidence — video may be static or corrupted")
    if video_clarity < 0.6:
        warnings.append("Low video clarity — resolution below 640x480")

    return {
        "overall_score": overall,
        "components": {
            "video_clarity": round(video_clarity, 2),
            "audio_quality": round(audio_quality, 2),
            "shot_detection_confidence": round(shot_conf, 2),
            "transcript_confidence": round(transcript_conf, 2),
        },
        "warnings": warnings,
    }


def build_processing_metadata(
    stages_completed: list[str],
    processing_duration_seconds: float,
    analyzer_version: str = "sws_analyzer_v1.0",
    timestamp: Optional[str] = None,
) -> dict:
    """
    Build processing_metadata.json from pipeline execution info.

    Args:
        stages_completed: List of completed stage names.
        processing_duration_seconds: Total processing time.
        analyzer_version: Version string of the analyzer.
        timestamp: ISO 8601 timestamp (defaults to now).

    Returns:
        processing_metadata.json-conformant dict.
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).isoformat()

    return {
        "analyzer_version": analyzer_version,
        "processing_timestamp": timestamp,
        "processing_duration_seconds": processing_duration_seconds,
        "stages_completed": stages_completed,
    }
