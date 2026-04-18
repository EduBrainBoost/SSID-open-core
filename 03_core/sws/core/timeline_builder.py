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


# --- Spec-required functions (Lane C contract) ---


def plan_shot_interventions(
    replacement_plan: dict,
    original_timeline: dict,
) -> list[dict]:
    """Plan brand interventions per shot from a replacement plan.

    Maps slot assignments to shots in the original timeline,
    determining what intervention type applies to each shot.

    Returns:
        List of ShotIntervention dicts.
    """
    shots = original_timeline.get("shots", [])
    slot_assignments = replacement_plan.get("slot_assignments", [])
    fps = 30.0

    interventions = []
    for shot in shots:
        shot_id = shot["shot_id"]
        shot_start = shot["start_frame"] / fps
        shot_end = shot["end_frame"] / fps

        # Find matching slots for this shot
        vis_slot_id = f"vis_{shot_id}"
        for slot in slot_assignments:
            if slot["slot_id"] == vis_slot_id:
                intervention_type = "VISUAL_EFFECT"
                if slot["slot_type"] == "text":
                    intervention_type = "TEXT_OVERLAY"
                elif slot["slot_type"] == "audio":
                    intervention_type = "AUDIO_SWAP"
                elif slot["slot_type"] in ("logo", "cta"):
                    intervention_type = "CTA_INSERTION"

                interventions.append({
                    "shot_id": shot_id,
                    "shot_num": int(shot_id.split("_")[1]),
                    "intervention_type": intervention_type,
                    "timing": {
                        "start_seconds": round(shot_start, 3),
                        "end_seconds": round(shot_end, 3),
                    },
                    "asset_ref": slot.get("replacement_ref", ""),
                    "strategy": slot.get("strategy", "keep_original"),
                })

    return interventions


def sequence_brand_interventions(
    interventions: list[dict],
    timing_rules: Optional[dict] = None,
) -> list[dict]:
    """Sequence and validate brand interventions against timing rules.

    Ensures no overlapping interventions within the same layer and
    that interventions honor original shot boundaries.

    Args:
        interventions: List of ShotIntervention dicts.
        timing_rules: Optional rules dict with max_overlap_ms, etc.

    Returns:
        Sorted, validated list of BrandIntervention dicts.
    """
    if timing_rules is None:
        timing_rules = {"max_overlap_ms": 0}

    # Sort by start time
    sorted_interventions = sorted(
        interventions,
        key=lambda x: x.get("timing", {}).get("start_seconds", 0),
    )

    # Validate no overlaps
    validated = []
    for intervention in sorted_interventions:
        timing = intervention.get("timing", {})
        start = timing.get("start_seconds", 0)
        end = timing.get("end_seconds", 0)

        conflict = False
        for existing in validated:
            ex_timing = existing.get("timing", {})
            ex_start = ex_timing.get("start_seconds", 0)
            ex_end = ex_timing.get("end_seconds", 0)
            if start < ex_end and end > ex_start:
                if existing.get("intervention_type") == intervention.get("intervention_type"):
                    conflict = True
                    break

        validated.append({
            **intervention,
            "sequenced": True,
            "has_conflict": conflict,
        })

    return validated


def compose_timeline(
    original: dict,
    interventions: list[dict],
) -> dict:
    """Compose a rebuilt timeline from original timeline and brand interventions.

    Produces a rebuild_timeline conforming to rebuild_timeline.schema with
    output_timeline.shot_updated matching original shot count.

    Returns:
        RebuiltTimeline dict.
    """
    shots = original.get("shots", [])
    fps = 30.0

    # Build segments from original shots
    segments = []
    for shot in shots:
        start_sec = shot["start_frame"] / fps
        end_sec = shot["end_frame"] / fps
        segments.append({
            "segment_id": f"tl_{shot['shot_id']}",
            "start_seconds": round(start_sec, 3),
            "end_seconds": round(end_sec, 3),
            "layer": "video",
            "asset_ref": f"original_{shot['shot_id']}",
            "transition_in": "cut",
            "transition_out": "cut",
        })

    # Build brand_interventions list
    brand_interventions = []
    intervention_by_shot = {}
    for intv in interventions:
        shot_id = intv.get("shot_id", "")
        brand_interventions.append({
            "shot_num": intv.get("shot_num", 0),
            "intervention_type": intv.get("intervention_type", "VISUAL_EFFECT"),
            "timing": intv.get("timing", {}),
            "asset_ref": intv.get("asset_ref", ""),
        })
        if shot_id not in intervention_by_shot:
            intervention_by_shot[shot_id] = []
        intervention_by_shot[shot_id].append(intv.get("intervention_type", ""))

    # Build output_timeline with shot_updated matching original count
    shot_updated = []
    for shot in shots:
        sid = shot["shot_id"]
        applied = intervention_by_shot.get(sid, [])
        shot_updated.append({
            "shot_id": sid,
            "modified": len(applied) > 0,
            "interventions_applied": applied,
        })

    timeline = {
        "schema_version": "1.0.0",
        "job_id": "composed",
        "attempt_id": "attempt_001",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "timeline_segments": segments,
        "brand_interventions": brand_interventions,
        "output_timeline": {"shot_updated": shot_updated},
        "render_plan": {
            "resolution": {"width": 1920, "height": 1080},
            "fps": fps,
            "codec": "h264",
            "bitrate_kbps": 2500,
            "format": "mp4",
            "audio_codec": "aac",
            "audio_bitrate_kbps": 128,
        },
    }
    timeline["output_hash"] = _hash_artifact(timeline)
    return timeline
