"""
Timeline Builder — timeline assembly from shot_timeline, beat_map, and replacement plan.

Shard: sws-render-engine
Produces: rebuild_timeline artifact
Consumes: replacement_plan, script_blueprint, brand_profile, platform_policy

Assembles a deterministic multi-layer timeline with render plan
specifications for ffmpeg-based video generation.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Optional


def _hash_artifact(data: dict) -> str:
    content = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(content).hexdigest()


def build_rebuild_timeline(
    shot_timeline: dict,
    replacement_plan: dict,
    job_id: str,
    attempt_id: str,
    beat_map: Optional[dict] = None,
    target_resolution: Optional[dict] = None,
    target_fps: float = 30.0,
    target_codec: str = "h264",
    target_bitrate_kbps: int = 2500,
    target_format: str = "mp4",
) -> dict:
    """
    Build a rebuild timeline from shot timeline and replacement plan.

    Merges visual, audio, voiceover, and overlay segments into
    a layered timeline with render specifications.

    Args:
        shot_timeline: Analyzed shot timeline artifact.
        replacement_plan: Replacement plan with slot assignments.
        job_id: Parent job identifier.
        attempt_id: Attempt identifier.
        beat_map: Optional beat map for music-aligned timing.
        target_resolution: Output resolution dict {width, height}.
        target_fps: Output frame rate.
        target_codec: Output video codec.
        target_bitrate_kbps: Output video bitrate.
        target_format: Output container format.

    Returns:
        rebuild_timeline artifact dict.
    """
    if target_resolution is None:
        target_resolution = {"width": 1920, "height": 1080}

    segments = []
    slot_map = {}
    for slot in replacement_plan.get("slot_assignments", []):
        slot_map[slot["slot_id"]] = slot

    # Video layer from shots
    shots = shot_timeline.get("shots", [])
    fps = target_fps
    for shot in shots:
        start_sec = shot["start_frame"] / fps if fps > 0 else 0
        end_sec = shot["end_frame"] / fps if fps > 0 else 0
        vis_slot_id = f"vis_{shot['shot_id']}"
        vis_slot = slot_map.get(vis_slot_id, {})
        asset_ref = vis_slot.get("replacement_ref", f"original_{shot['shot_id']}")

        transition_in = "cut"
        if shot.get("scene_type") == "transition_fade":
            transition_in = "fade"

        segments.append({
            "segment_id": f"tl_video_{shot['shot_id']}",
            "start_seconds": round(start_sec, 3),
            "end_seconds": round(end_sec, 3),
            "layer": "video",
            "asset_ref": asset_ref,
            "transition_in": transition_in,
            "transition_out": "cut",
        })

    # Voiceover layer from replacement plan
    vo_slots = [s for s in replacement_plan.get("slot_assignments", []) if s["slot_type"] == "voiceover"]
    for i, slot in enumerate(vo_slots):
        # Distribute voiceover across timeline proportionally
        total_duration = shots[-1]["end_frame"] / fps if shots and fps > 0 else 300
        segment_duration = total_duration / max(len(vo_slots), 1)
        start = round(i * segment_duration, 3)
        end = round((i + 1) * segment_duration, 3)
        segments.append({
            "segment_id": f"tl_vo_{slot['slot_id']}",
            "start_seconds": start,
            "end_seconds": end,
            "layer": "voiceover",
            "asset_ref": slot["replacement_ref"],
            "transition_in": "none",
            "transition_out": "none",
        })

    # Music layer from beat_map (if available)
    if beat_map and beat_map.get("beat_grid"):
        total_duration = shots[-1]["end_frame"] / fps if shots and fps > 0 else 300
        segments.append({
            "segment_id": "tl_music_main",
            "start_seconds": 0,
            "end_seconds": round(total_duration, 3),
            "layer": "music",
            "asset_ref": f"music_bpm_{beat_map.get('bpm', 120)}",
            "transition_in": "fade",
            "transition_out": "fade",
        })

    render_plan = {
        "resolution": target_resolution,
        "fps": target_fps,
        "codec": target_codec,
        "bitrate_kbps": target_bitrate_kbps,
        "format": target_format,
        "audio_codec": "aac",
        "audio_bitrate_kbps": 128,
    }

    timeline = {
        "schema_version": "1.0.0",
        "job_id": job_id,
        "attempt_id": attempt_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "timeline_segments": segments,
        "render_plan": render_plan,
    }
    timeline["output_hash"] = _hash_artifact(timeline)
    return timeline


def validate_rebuild_timeline(timeline: dict) -> list[str]:
    """
    Validate a rebuild timeline for completeness and consistency.

    Returns:
        List of validation errors (empty if valid).
    """
    errors = []
    required = [
        "schema_version", "job_id", "attempt_id", "created_at_utc",
        "timeline_segments", "render_plan", "output_hash",
    ]
    for key in required:
        if key not in timeline:
            errors.append(f"Missing required field: {key}")

    segments = timeline.get("timeline_segments", [])
    for seg in segments:
        for k in ("segment_id", "start_seconds", "end_seconds", "layer", "asset_ref"):
            if k not in seg:
                errors.append(f"Segment missing required field: {k}")
        if "start_seconds" in seg and "end_seconds" in seg:
            if seg["end_seconds"] < seg["start_seconds"]:
                errors.append(f"Segment {seg.get('segment_id')}: end < start")

    rp = timeline.get("render_plan", {})
    for k in ("resolution", "fps", "codec", "bitrate_kbps", "format"):
        if k not in rp:
            errors.append(f"render_plan missing required field: {k}")

    return errors


def compute_timeline_duration(timeline: dict) -> float:
    """Return the total duration of the timeline in seconds."""
    segments = timeline.get("timeline_segments", [])
    if not segments:
        return 0.0
    return max(seg.get("end_seconds", 0) for seg in segments)
