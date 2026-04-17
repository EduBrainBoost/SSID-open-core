"""
Transcript pipeline for SWS Analyze Spine.

Handles speech-to-text extraction from audio tracks.
Produces transcript_master.json-conformant output.

External STT backends (Whisper, etc.) are injected via the TranscriptBackend protocol.
A synthetic backend is provided for testing.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass
class TranscriptSegment:
    """A single transcript segment."""

    segment_id: int
    start_time: float
    end_time: float
    text: str
    confidence: float


@runtime_checkable
class TranscriptBackend(Protocol):
    """Protocol for pluggable STT backends."""

    def transcribe(self, audio_path: Path, language: str) -> list[TranscriptSegment]:
        """Transcribe audio file and return ordered segments."""
        ...


class SyntheticTranscriptBackend:
    """Deterministic synthetic backend for testing. Produces fixed segments."""

    # Deterministic confidence values matching golden test fixtures
    CONFIDENCE_VALUES = [0.89, 0.91, 0.88]

    def __init__(self, segment_duration: float = 100.0, num_segments: int = 3):
        self._segment_duration = segment_duration
        self._num_segments = num_segments

    def transcribe(self, audio_path: Path, language: str) -> list[TranscriptSegment]:
        segments = []
        for i in range(self._num_segments):
            conf = self.CONFIDENCE_VALUES[i] if i < len(self.CONFIDENCE_VALUES) else 0.85
            segments.append(
                TranscriptSegment(
                    segment_id=i + 1,
                    start_time=i * self._segment_duration,
                    end_time=(i + 1) * self._segment_duration,
                    text=f"[Synthetic test audio segment {i + 1}]",
                    confidence=conf,
                )
            )
        return segments


def run_transcript_pipeline(
    audio_path: Path,
    language: str = "en",
    backend: TranscriptBackend | None = None,
) -> dict:
    """
    Run the transcript pipeline on an audio file.

    Args:
        audio_path: Path to the audio/video file.
        language: BCP-47 language tag.
        backend: STT backend to use. Defaults to SyntheticTranscriptBackend.

    Returns:
        transcript_master.json-conformant dict.
    """
    if backend is None:
        backend = SyntheticTranscriptBackend()

    segments = backend.transcribe(audio_path, language)

    segment_dicts = []
    texts = []
    for seg in segments:
        segment_dicts.append({
            "segment_id": seg.segment_id,
            "start_time": seg.start_time,
            "end_time": seg.end_time,
            "text": seg.text,
            "confidence": seg.confidence,
        })
        texts.append(seg.text)

    return {
        "transcript_id": f"transcript_v1",
        "language": language,
        "segments": segment_dicts,
        "full_text": " ".join(texts),
    }
