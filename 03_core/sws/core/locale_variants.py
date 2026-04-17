"""
Locale Variants — multi-language/region adaptation engine.

Shard: sws-locale-service
Produces: locale_variants artifact
Consumes: script_blueprint, brand_profile, platform_policy

Generates locale-specific content variants with timing adjustments
and review state tracking for multilingual content delivery.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Optional


def _hash_artifact(data: dict) -> str:
    content = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(content).hexdigest()


def build_locale_variants(
    script_blueprint: dict,
    target_locales: list[str],
    primary_locale: str,
    job_id: str,
    attempt_id: str,
    translation_map: Optional[dict[str, dict[str, str]]] = None,
) -> dict:
    """
    Build locale variants from a script blueprint.

    For each target locale, generates localized script segments
    with timing offsets. Uses translation_map if provided,
    otherwise marks segments for translation.

    Args:
        script_blueprint: Script blueprint artifact with segments.
        target_locales: List of BCP-47 locale codes to generate.
        primary_locale: BCP-47 code of the primary locale.
        job_id: Parent job identifier.
        attempt_id: Attempt identifier.
        translation_map: Optional dict of locale -> {segment_id: translated_text}.

    Returns:
        locale_variants artifact dict.
    """
    if translation_map is None:
        translation_map = {}

    segments = script_blueprint.get("segments", [])
    variants = []

    for locale in target_locales:
        locale_translations = translation_map.get(locale, {})
        script_segments = []

        for seg in segments:
            seg_id = str(seg.get("segment_id", ""))
            original_text = seg.get("text", "")

            if locale == primary_locale:
                text = original_text
                timing_offset_ms = 0
            elif seg_id in locale_translations:
                text = locale_translations[seg_id]
                # Estimate timing adjustment based on text length difference
                len_ratio = len(text) / max(len(original_text), 1)
                timing_offset_ms = int((len_ratio - 1.0) * 500)
            else:
                text = f"[UNTRANSLATED:{locale}] {original_text}"
                timing_offset_ms = 0

            entry = {
                "segment_id": seg_id,
                "text": text,
                "timing_offset_ms": timing_offset_ms,
            }
            script_segments.append(entry)

        review_status = "auto_approved" if locale == primary_locale else "pending"
        if locale in locale_translations:
            review_status = "pending"

        variant = {
            "locale": locale,
            "script_segments": script_segments,
            "review_status": review_status,
        }
        variants.append(variant)

    result = {
        "schema_version": "1.0.0",
        "job_id": job_id,
        "attempt_id": attempt_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "primary_locale": primary_locale,
        "variants": variants,
    }
    result["output_hash"] = _hash_artifact(result)
    return result


def validate_locale_variants(variants_artifact: dict) -> list[str]:
    """
    Validate a locale variants artifact.

    Returns:
        List of validation errors (empty if valid).
    """
    errors = []
    required = [
        "schema_version", "job_id", "attempt_id", "created_at_utc",
        "primary_locale", "variants", "output_hash",
    ]
    for key in required:
        if key not in variants_artifact:
            errors.append(f"Missing required field: {key}")

    primary = variants_artifact.get("primary_locale", "")
    variants = variants_artifact.get("variants", [])

    primary_found = False
    for v in variants:
        for k in ("locale", "script_segments", "review_status"):
            if k not in v:
                errors.append(f"Variant missing required field: {k}")
        if v.get("locale") == primary:
            primary_found = True
        for seg in v.get("script_segments", []):
            for k in ("segment_id", "text", "timing_offset_ms"):
                if k not in seg:
                    errors.append(f"Segment missing required field: {k}")

    if primary and variants and not primary_found:
        errors.append(f"Primary locale '{primary}' not found in variants")

    return errors


def get_approved_locales(variants_artifact: dict) -> list[str]:
    """Return list of locale codes with approved or auto_approved status."""
    return [
        v["locale"]
        for v in variants_artifact.get("variants", [])
        if v.get("review_status") in ("approved", "auto_approved")
    ]
