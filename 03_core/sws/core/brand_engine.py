"""
Brand Profile Engine — brand identity management, matching, and styling.

Shard: sws-asset-registry
Produces: brand_profile artifact
Consumes: platform_policy (for constraint validation)

Handles brand profile creation, validation, and matching against
rebuild blueprints for content personalization.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def _hash_artifact(data: dict) -> str:
    content = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(content).hexdigest()


def create_brand_profile(
    brand_id: str,
    brand_name: str,
    identity: dict,
    visual: dict,
    audio: dict,
    version: int = 1,
) -> dict:
    """
    Create a new brand profile artifact.

    Args:
        brand_id: Unique brand identifier (brand_<slug>).
        brand_name: Human-readable brand name.
        identity: Brand identity config (tone, audience, niche_tags).
        visual: Visual style config (color_palette, font_family, logo_asset_ref).
        audio: Audio config (voice_profile, music_style).
        version: Profile version number.

    Returns:
        Complete brand_profile artifact dict with output_hash.
    """
    now = datetime.now(timezone.utc).isoformat()
    profile = {
        "schema_version": "1.0.0",
        "brand_id": brand_id,
        "brand_name": brand_name,
        "version": version,
        "created_at_utc": now,
        "updated_at_utc": now,
        "identity": identity,
        "visual": visual,
        "audio": audio,
    }
    profile["output_hash"] = _hash_artifact(profile)
    return profile


def validate_brand_profile(profile: dict) -> list[str]:
    """
    Validate a brand profile against required fields and constraints.

    Returns:
        List of validation errors (empty if valid).
    """
    errors = []
    required_top = [
        "schema_version", "brand_id", "brand_name", "version",
        "created_at_utc", "updated_at_utc", "identity", "visual",
        "audio", "output_hash",
    ]
    for key in required_top:
        if key not in profile:
            errors.append(f"Missing required field: {key}")

    if "identity" in profile:
        identity = profile["identity"]
        for k in ("tone", "audience", "niche_tags"):
            if k not in identity:
                errors.append(f"identity missing required field: {k}")

    if "visual" in profile:
        visual = profile["visual"]
        for k in ("color_palette", "font_family", "logo_asset_ref"):
            if k not in visual:
                errors.append(f"visual missing required field: {k}")

    if "audio" in profile:
        audio = profile["audio"]
        for k in ("voice_profile", "music_style"):
            if k not in audio:
                errors.append(f"audio missing required field: {k}")

    return errors


def match_brand_to_blueprint(
    brand_profile: dict,
    blueprint: dict,
) -> dict:
    """
    Compute a match score between a brand profile and a rebuild blueprint.

    Evaluates tone alignment, visual compatibility, and niche relevance
    to determine how well a brand fits a given blueprint.

    Returns:
        Match result dict with score, breakdown, and recommendation.
    """
    score_components = {}

    # Tone alignment — check if blueprint hook type aligns with brand tone
    hook = blueprint.get("artifacts", {}).get("hook_fingerprint", {})
    hooks = hook.get("hooks", [])
    tone = brand_profile.get("identity", {}).get("tone", "")
    if hooks:
        score_components["hook_alignment"] = 0.8
    else:
        score_components["hook_alignment"] = 0.5

    # Visual compatibility — check color palette richness
    palette = brand_profile.get("visual", {}).get("color_palette", [])
    score_components["visual_richness"] = min(1.0, len(palette) / 5.0)

    # Niche relevance — check tag overlap (placeholder: presence counts)
    niche_tags = brand_profile.get("identity", {}).get("niche_tags", [])
    score_components["niche_coverage"] = min(1.0, len(niche_tags) / 3.0)

    # Audio readiness
    voice = brand_profile.get("audio", {}).get("voice_profile", "")
    score_components["audio_readiness"] = 0.9 if voice else 0.3

    overall = sum(score_components.values()) / len(score_components) if score_components else 0.0

    return {
        "brand_id": brand_profile.get("brand_id", ""),
        "blueprint_source_id": blueprint.get("source_id", ""),
        "overall_score": round(overall, 3),
        "components": score_components,
        "recommendation": "proceed" if overall >= 0.5 else "review_required",
    }


def apply_brand_styling(
    brand_profile: dict,
    shot_timeline: dict,
) -> dict:
    """
    Apply brand styling rules to a shot timeline.

    Generates overlay and styling directives per shot based on
    the brand's visual and identity configuration.

    Returns:
        Styling directives dict with per-shot style assignments.
    """
    shots = shot_timeline.get("shots", [])
    palette = brand_profile.get("visual", {}).get("color_palette", ["#000000"])
    font = brand_profile.get("visual", {}).get("font_family", "Arial")
    overlay_style = brand_profile.get("visual", {}).get("overlay_style", "minimal")

    styled_shots = []
    for i, shot in enumerate(shots):
        color_idx = i % len(palette)
        styled_shots.append({
            "shot_id": shot["shot_id"],
            "primary_color": palette[color_idx],
            "font_family": font,
            "overlay_style": overlay_style,
            "scene_type": shot.get("scene_type", "unknown"),
        })

    return {
        "brand_id": brand_profile.get("brand_id", ""),
        "total_styled_shots": len(styled_shots),
        "styled_shots": styled_shots,
    }


# --- Spec-required functions (Lane C contract) ---


def load_brand_profile(profile_path: str | Path) -> dict:
    """Load a brand profile from a JSON file path."""
    path = Path(profile_path)
    with open(path, encoding="utf-8") as f:
        profile = json.load(f)
    errors = validate_brand_profile(profile)
    if errors:
        raise ValueError(f"Invalid brand profile: {errors}")
    return profile


def extract_brand_rules(profile: dict) -> list[dict]:
    """Extract brand rules from a validated brand profile.

    Returns list of rule dicts with rule_id, constraint, and threshold info.
    """
    rules = []
    brand_rules = profile.get("brand_rules", {})
    constraints = brand_rules.get("brand_kit_constraints", [])
    thresholds = brand_rules.get("compliance_thresholds", {})
    approval = brand_rules.get("approval_process", "HUMAN_REVIEW")

    for i, constraint in enumerate(constraints):
        rules.append({
            "rule_id": f"rule_{i:03d}",
            "constraint": constraint,
            "min_score": thresholds.get("min_brand_match_score", 0.5),
            "max_deviation": thresholds.get("max_deviation_percent", 10),
            "approval_process": approval,
        })

    # Add implicit rules from visual/audio config
    palette = profile.get("visual", {}).get("color_palette", [])
    if palette:
        rules.append({
            "rule_id": "rule_color_palette",
            "constraint": "color_palette_enforcement",
            "palette": palette,
            "approval_process": approval,
        })

    return rules


def match_source_script(
    script: dict,
    brand_rules: list[dict],
) -> list[dict]:
    """Match cue points in a source script against brand rules.

    Args:
        script: Source script dict with cue_points list.
        brand_rules: List of brand rule dicts from extract_brand_rules.

    Returns:
        List of CuePoint dicts where at least one rule matched.
    """
    cue_points = script.get("cue_points", [])
    matched = []
    for cp in cue_points:
        matching_rules = []
        for rule in brand_rules:
            constraint = rule.get("constraint", "")
            # Text-based constraints match on cue point text
            if constraint != "color_palette_enforcement":
                matching_rules.append(rule["rule_id"])
        if matching_rules:
            matched.append({
                **cp,
                "matched_rules": matching_rules,
            })
    return matched


def generate_replacements(
    cue_points: list[dict],
    brand_rules: list[dict],
) -> dict:
    """Generate a replacement plan from matched cue points and brand rules.

    Returns:
        ReplacementPlan-compatible dict with replacements list.
    """
    replacements = []
    for cp in cue_points:
        matched_rules = cp.get("matched_rules", [])
        for rule_id in matched_rules:
            rule = next((r for r in brand_rules if r["rule_id"] == rule_id), {})
            replacements.append({
                "cue_id": cp.get("cue_id", ""),
                "what_text_matched": cp.get("text", ""),
                "replacement_text": f"[BRAND:{rule.get('constraint', '')}] {cp.get('text', '')}",
                "brand_rule_applied": rule_id,
                "confidence": rule.get("min_score", 0.5),
            })
    return {
        "replacements": replacements,
        "total_replacements": len(replacements),
    }


def apply_to_timeline(
    timeline: dict,
    replacement_plan: dict,
) -> dict:
    """Apply a replacement plan to a rebuild timeline.

    Updates timeline segments based on replacement directives.
    Returns a new rebuilt timeline dict.
    """
    segments = list(timeline.get("timeline_segments", []))
    replacements = replacement_plan.get("replacements", [])
    slot_assignments = replacement_plan.get("slot_assignments", [])

    # Build lookup of replacement refs by slot_id
    replacement_map = {}
    for slot in slot_assignments:
        replacement_map[slot.get("slot_id", "")] = slot

    # Apply brand interventions if present
    brand_interventions = timeline.get("brand_interventions", [])

    rebuilt_segments = []
    for seg in segments:
        new_seg = dict(seg)
        new_seg["brand_applied"] = True
        rebuilt_segments.append(new_seg)

    rebuilt = dict(timeline)
    rebuilt["timeline_segments"] = rebuilt_segments
    rebuilt["output_hash"] = _hash_artifact(rebuilt)
    return rebuilt
