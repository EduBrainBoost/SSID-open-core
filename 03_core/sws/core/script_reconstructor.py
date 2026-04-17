"""
Script Reconstructor — script and replacement plan generation from blueprints.

Shard: sws-replacement-engine
Produces: replacement_plan, script_blueprint artifacts
Consumes: rebuild_blueprint, brand_profile, platform_policy

Reconstructs content scripts from analyzed blueprints, mapping
each element to brand-safe replacements with full provenance tracking.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Optional


def _hash_artifact(data: dict) -> str:
    content = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(content).hexdigest()


def build_replacement_plan(
    blueprint: dict,
    brand_profile: dict,
    job_id: str,
    attempt_id: str,
    asset_provenance: Optional[list[dict]] = None,
) -> dict:
    """
    Build a replacement plan from a blueprint and brand profile.

    Maps each rebuild slot from the blueprint to a brand-appropriate
    replacement with strategy and provenance tracking.

    Args:
        blueprint: Rebuild blueprint artifact.
        brand_profile: Target brand profile.
        job_id: Parent job identifier.
        attempt_id: Attempt identifier.
        asset_provenance: Pre-existing provenance records.

    Returns:
        replacement_plan artifact dict.
    """
    blueprint_id = blueprint.get("source_id", "unknown")
    brand_id = brand_profile.get("brand_id", "unknown")
    artifacts = blueprint.get("artifacts", {})

    slot_assignments = []
    provenance_refs = list(asset_provenance or [])
    provenance_asset_ids = {p["asset_id"] for p in provenance_refs}

    # Map transcript segments to voiceover slots
    transcript = artifacts.get("transcript_master", {})
    for seg in transcript.get("segments", []):
        slot_id = f"vo_{seg.get('segment_id', 'unknown')}"
        replacement_ref = f"brand_voice_{brand_id}_{seg.get('segment_id', '')}"
        slot_assignments.append({
            "slot_id": slot_id,
            "slot_type": "voiceover",
            "source_ref": f"transcript.segment_{seg.get('segment_id', '')}",
            "replacement_ref": replacement_ref,
            "strategy": "generate",
            "confidence": 0.85,
        })
        if replacement_ref not in provenance_asset_ids:
            provenance_refs.append({
                "asset_id": replacement_ref,
                "license_status": "generated",
                "origin_type": "generated",
            })
            provenance_asset_ids.add(replacement_ref)

    # Map shots to visual slots
    shot_timeline = artifacts.get("shot_timeline", {})
    for shot in shot_timeline.get("shots", []):
        slot_id = f"vis_{shot['shot_id']}"
        replacement_ref = f"brand_visual_{brand_id}_{shot['shot_id']}"
        strategy = "style_transfer" if shot.get("scene_type") != "unknown" else "keep_original"
        slot_assignments.append({
            "slot_id": slot_id,
            "slot_type": "visual",
            "source_ref": f"shot_timeline.{shot['shot_id']}",
            "replacement_ref": replacement_ref,
            "strategy": strategy,
            "confidence": shot.get("confidence", 0.5),
        })
        if replacement_ref not in provenance_asset_ids:
            provenance_refs.append({
                "asset_id": replacement_ref,
                "license_status": "generated",
                "origin_type": "generated",
            })
            provenance_asset_ids.add(replacement_ref)

    # Add brand logo as CTA slot
    logo_ref = brand_profile.get("visual", {}).get("logo_asset_ref", "")
    if logo_ref:
        slot_assignments.append({
            "slot_id": "cta_logo",
            "slot_type": "logo",
            "source_ref": "brand_profile.visual.logo_asset_ref",
            "replacement_ref": logo_ref,
            "strategy": "direct_replace",
            "confidence": 1.0,
        })
        if logo_ref not in provenance_asset_ids:
            provenance_refs.append({
                "asset_id": logo_ref,
                "license_status": "owned",
                "origin_type": "uploaded",
            })

    # Build source_script from transcript
    full_text = transcript.get("full_text", "")
    cue_points = []
    for seg in transcript.get("segments", []):
        cue_points.append({
            "cue_id": f"cue_{seg.get('segment_id', '')}",
            "time_seconds": seg.get("start_time", 0.0),
            "text": seg.get("text", ""),
        })

    source_script = {
        "original_text": full_text,
        "speaker_map": {},
        "cue_points": cue_points,
    }

    # Build locale_info from brand profile
    lang_primary = brand_profile.get("identity", {}).get("language_primary", "en")
    locale_info = {
        "language": lang_primary,
        "region": "US" if lang_primary == "en" else lang_primary.upper(),
    }

    plan = {
        "schema_version": "1.0.0",
        "job_id": job_id,
        "attempt_id": attempt_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "blueprint_id": blueprint_id,
        "brand_id": brand_id,
        "slot_assignments": slot_assignments,
        "asset_provenance_refs": provenance_refs,
        "source_script": source_script,
        "locale_info": locale_info,
    }
    plan["output_hash"] = _hash_artifact(plan)
    return plan


def build_script_blueprint(
    blueprint: dict,
    replacement_plan: dict,
    brand_profile: dict,
    job_id: str,
    attempt_id: str,
) -> dict:
    """
    Reconstruct a script blueprint from replacement plan and brand profile.

    Assembles text, timing, and styling for each script segment based on
    the replacement assignments.

    Returns:
        script_blueprint artifact dict.
    """
    blueprint_id = blueprint.get("source_id", "unknown")
    transcript = blueprint.get("artifacts", {}).get("transcript_master", {})
    voice_profile = brand_profile.get("audio", {}).get("voice_profile", "default")

    segments = []
    for seg in transcript.get("segments", []):
        segments.append({
            "segment_id": str(seg.get("segment_id", "")),
            "text": seg.get("text", ""),
            "start_seconds": seg.get("start_time", 0.0),
            "end_seconds": seg.get("end_time", 0.0),
            "voice_profile": voice_profile,
            "style": {
                "tone": brand_profile.get("identity", {}).get("tone", "professional"),
                "emphasis": "normal",
            },
        })

    script = {
        "schema_version": "1.0.0",
        "job_id": job_id,
        "attempt_id": attempt_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "blueprint_id": blueprint_id,
        "segments": segments,
        "seed": _hash_artifact({"blueprint_id": blueprint_id, "job_id": job_id}),
    }
    script["output_hash"] = _hash_artifact(script)
    return script


def validate_replacement_plan(plan: dict) -> list[str]:
    """
    Validate a replacement plan for completeness and consistency.

    Returns:
        List of validation errors (empty if valid).
    """
    errors = []
    required = [
        "schema_version", "job_id", "attempt_id", "created_at_utc",
        "blueprint_id", "brand_id", "slot_assignments",
        "asset_provenance_refs", "output_hash",
        "source_script", "locale_info",
    ]
    for key in required:
        if key not in plan:
            errors.append(f"Missing required field: {key}")

    slots = plan.get("slot_assignments", [])
    for slot in slots:
        for k in ("slot_id", "slot_type", "source_ref", "replacement_ref", "strategy"):
            if k not in slot:
                errors.append(f"Slot missing required field: {k}")

    # Check provenance coverage
    replacement_refs = {s.get("replacement_ref") for s in slots if s.get("strategy") != "keep_original"}
    provenance_ids = {p.get("asset_id") for p in plan.get("asset_provenance_refs", [])}
    missing_provenance = replacement_refs - provenance_ids
    if missing_provenance:
        errors.append(f"Missing provenance for assets: {missing_provenance}")

    return errors


# --- Spec-required functions (Lane C contract) ---


def extract_speaker_map(transcript_master: dict) -> dict[str, str]:
    """Extract speaker map from a transcript master.

    Returns dict of {speaker_id: speaker_name}.
    If transcript has no explicit speaker info, creates synthetic entries.
    """
    segments = transcript_master.get("segments", [])
    speaker_map = {}
    for seg in segments:
        speaker_id = str(seg.get("speaker_id", seg.get("segment_id", "")))
        speaker_name = seg.get("speaker_name", f"Speaker_{speaker_id}")
        if speaker_id not in speaker_map:
            speaker_map[speaker_id] = speaker_name
    return speaker_map


def extract_cue_points(
    shot_timeline: dict,
    transcript_master: dict,
) -> list[dict]:
    """Extract cue points by correlating shot timeline with transcript segments.

    Each cue point links a time, speaker, text, and scene context.

    Returns:
        List of CuePoint dicts.
    """
    shots = shot_timeline.get("shots", [])
    segments = transcript_master.get("segments", [])
    fps = 30.0

    cue_points = []
    for seg in segments:
        start_time = seg.get("start_time", 0.0)
        end_time = seg.get("end_time", 0.0)
        mid_time = (start_time + end_time) / 2.0

        scene_context = "unknown"
        for shot in shots:
            shot_start_sec = shot["start_frame"] / fps
            shot_end_sec = shot["end_frame"] / fps
            if shot_start_sec <= mid_time < shot_end_sec:
                scene_context = shot.get("scene_type", "unknown")
                break

        speaker_id = str(seg.get("speaker_id", seg.get("segment_id", "")))
        cue_points.append({
            "cue_id": f"cue_{seg.get('segment_id', '')}",
            "time_seconds": start_time,
            "speaker_id": speaker_id,
            "text": seg.get("text", ""),
            "scene_context": scene_context,
        })

    return cue_points


def build_editable_script(cue_points: list[dict]) -> dict:
    """Build an editable script document from cue points.

    Returns:
        ScriptDocument dict with lines containing line_number, timing,
        speaker_label, and text.
    """
    lines = []
    for i, cp in enumerate(cue_points):
        lines.append({
            "line_number": i + 1,
            "timing_seconds": cp.get("time_seconds", 0.0),
            "speaker_label": cp.get("speaker_id", ""),
            "text": cp.get("text", ""),
            "scene_context": cp.get("scene_context", "unknown"),
        })

    return {
        "format": "editable_script",
        "version": "1.0",
        "total_lines": len(lines),
        "lines": lines,
    }
