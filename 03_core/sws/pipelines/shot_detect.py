"""
Shot detection pipeline for SWS Analyze Spine.

Detects shot boundaries (cuts, fades, dissolves) and classifies scene types.
Produces shot_timeline.json-conformant output.

External detection backends (PySceneDetect, etc.) are injected via ShotDetectBackend.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass
class Shot:
    """A detected shot with boundary and classification."""

    shot_id: str
    start_frame: int
    end_frame: int
    duration_seconds: float
    scene_type: str
    confidence: float


@runtime_checkable
class ShotDetectBackend(Protocol):
    """Protocol for pluggable shot detection backends."""

    def detect_shots(self, video_path: Path, frame_rate: float) -> list[Shot]:
        """Detect shots in video. Returns ordered shot list."""
        ...


class SyntheticShotDetectBackend:
    """Deterministic synthetic backend for testing."""

    def __init__(self, total_frames: int = 9000, frame_rate: float = 30.0):
        self._total_frames = total_frames
        self._frame_rate = frame_rate

    def detect_shots(self, video_path: Path, frame_rate: float) -> list[Shot]:
        fr = frame_rate or self._frame_rate
        third = self._total_frames // 3
        scene_types = ["opening_static", "transition_fade", "closing_static"]
        confidences = [0.95, 0.87, 0.92]

        shots = []
        for i in range(3):
            start = i * third
            end = (i + 1) * third
            shots.append(
                Shot(
                    shot_id=f"shot_{i + 1:03d}",
                    start_frame=start,
                    end_frame=end,
                    duration_seconds=round((end - start) / fr, 2),
                    scene_type=scene_types[i],
                    confidence=confidences[i],
                )
            )
        return shots


def run_shot_detect_pipeline(
    video_path: Path,
    frame_rate: float = 30.0,
    backend: ShotDetectBackend | None = None,
) -> dict:
    """
    Run shot detection on a video file.

    Args:
        video_path: Path to the video file.
        frame_rate: Video frame rate.
        backend: Shot detection backend. Defaults to SyntheticShotDetectBackend.

    Returns:
        shot_timeline.json-conformant dict.
    """
    if backend is None:
        backend = SyntheticShotDetectBackend()

    shots = backend.detect_shots(video_path, frame_rate)

    return {
        "shots": [
            {
                "shot_id": s.shot_id,
                "start_frame": s.start_frame,
                "end_frame": s.end_frame,
                "duration_seconds": s.duration_seconds,
                "scene_type": s.scene_type,
                "confidence": s.confidence,
            }
            for s in shots
        ],
        "total_shots": len(shots),
    }
