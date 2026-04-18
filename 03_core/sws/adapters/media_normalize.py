"""
Media normalization adapter for SWS Analyze Spine.

Handles:
- Probe media files for technical metadata (resolution, codec, duration, etc.)
- Normalize audio channels (mono-to-stereo mapping)
- Generate media_technical and audio_map artifacts
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class MediaProbe:
    """Technical metadata extracted from a media file."""

    width: int
    height: int
    aspect_ratio: str
    duration_seconds: float
    frame_rate: float
    total_frames: int
    video_codec: str
    video_profile: str
    audio_codec: str
    audio_sample_rate: int
    audio_channels: int
    bitrate_video_kbps: int
    bitrate_audio_kbps: int
    pix_fmt: str


class ProbeError(Exception):
    """Raised when media probing fails."""


def probe_media(file_path: str | Path) -> MediaProbe:
    """
    Probe a media file using ffprobe to extract technical metadata.

    Falls back to a synthetic probe if ffprobe is not available,
    using file extension heuristics.

    Args:
        file_path: Path to the media file.

    Returns:
        MediaProbe with extracted metadata.
    """
    path = Path(file_path)
    if not path.exists():
        raise ProbeError(f"File does not exist: {path}")

    try:
        return _probe_with_ffprobe(path)
    except (FileNotFoundError, OSError):
        raise ProbeError(
            f"ffprobe not available. Install ffmpeg to probe media files. "
            f"File: {path}"
        )


def _probe_with_ffprobe(path: Path) -> MediaProbe:
    """Run ffprobe and parse output."""
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise ProbeError(f"ffprobe failed: {result.stderr}")

    data = json.loads(result.stdout)
    video_stream = next(
        (s for s in data.get("streams", []) if s["codec_type"] == "video"), None
    )
    audio_stream = next(
        (s for s in data.get("streams", []) if s["codec_type"] == "audio"), None
    )

    if video_stream is None:
        raise ProbeError("No video stream found")

    fmt = data.get("format", {})
    duration = float(fmt.get("duration", video_stream.get("duration", 0)))
    fr_parts = video_stream.get("r_frame_rate", "30/1").split("/")
    frame_rate = float(fr_parts[0]) / float(fr_parts[1]) if len(fr_parts) == 2 else 30.0
    width = int(video_stream.get("width", 0))
    height = int(video_stream.get("height", 0))

    if width > 0 and height > 0:
        from math import gcd
        g = gcd(width, height)
        aspect_ratio = f"{width // g}:{height // g}"
    else:
        aspect_ratio = "unknown"

    total_frames = int(round(duration * frame_rate))
    v_bitrate = int(video_stream.get("bit_rate", 0)) // 1000 or int(
        float(fmt.get("bit_rate", 0)) * 0.85
    ) // 1000
    a_bitrate = int(audio_stream.get("bit_rate", 128000)) // 1000 if audio_stream else 128

    return MediaProbe(
        width=width,
        height=height,
        aspect_ratio=aspect_ratio,
        duration_seconds=duration,
        frame_rate=frame_rate,
        total_frames=total_frames,
        video_codec=video_stream.get("codec_name", "unknown"),
        video_profile=video_stream.get("profile", "unknown").lower(),
        audio_codec=audio_stream.get("codec_name", "unknown") if audio_stream else "none",
        audio_sample_rate=int(audio_stream.get("sample_rate", 0)) if audio_stream else 0,
        audio_channels=int(audio_stream.get("channels", 0)) if audio_stream else 0,
        bitrate_video_kbps=v_bitrate,
        bitrate_audio_kbps=a_bitrate,
        pix_fmt=video_stream.get("pix_fmt", "unknown"),
    )


def build_media_technical(probe: MediaProbe) -> dict:
    """Build media_technical.json-conformant dict from probe data."""
    return {
        "resolution": {
            "width": probe.width,
            "height": probe.height,
            "aspect_ratio": probe.aspect_ratio,
        },
        "temporal": {
            "duration_seconds": probe.duration_seconds,
            "frame_rate": probe.frame_rate,
            "total_frames": probe.total_frames,
        },
        "codec": {
            "video_codec": probe.video_codec,
            "video_profile": probe.video_profile,
            "audio_codec": probe.audio_codec,
            "audio_sample_rate": probe.audio_sample_rate,
            "audio_channels": probe.audio_channels,
        },
        "quality_metrics": {
            "bitrate_video_kbps": probe.bitrate_video_kbps,
            "bitrate_audio_kbps": probe.bitrate_audio_kbps,
            "pix_fmt": probe.pix_fmt,
        },
    }


def build_audio_map(probe: MediaProbe, target_channels: int = 2) -> dict:
    """
    Build audio_map.json from probe data.

    Describes how source audio channels map to output channels.
    If source is mono and target is stereo, applies mono-to-stereo duplication.
    """
    source_ch = probe.audio_channels
    channel_map = {}

    if source_ch == 0:
        return {
            "source_channels": 0,
            "output_channels": 0,
            "channel_map": {},
        }

    if source_ch == 1 and target_channels == 2:
        channel_map["channel_0"] = {
            "type": "mono_to_stereo",
            "left_source": 0,
            "right_source": 0,
        }
    elif source_ch == target_channels:
        for i in range(source_ch):
            channel_map[f"channel_{i}"] = {
                "type": "passthrough",
                "source": i,
            }
    else:
        for i in range(min(source_ch, target_channels)):
            channel_map[f"channel_{i}"] = {
                "type": "remap",
                "source": i,
            }

    return {
        "source_channels": source_ch,
        "output_channels": target_channels,
        "channel_map": channel_map,
    }
