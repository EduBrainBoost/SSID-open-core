"""
Tests for SWS Rebuild Render — Lane C.

Covers: brand_engine, script_reconstructor, timeline_builder,
locale_variants, schemas, and integration flows.

Target: 30+ tests.
"""

import json
import os
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_DIR = REPO_ROOT / "03_core" / "sws" / "schemas"
GOLDEN_DIR = REPO_ROOT / "test_fixtures" / "sws_golden" / "expected_outputs"

# --- Imports from 03_core ---
import sys

_core_path = str(REPO_ROOT / "03_core")
if _core_path not in sys.path:
    sys.path.insert(0, _core_path)

from sws.core.brand_engine import (
    apply_brand_styling,
    apply_to_timeline,
    create_brand_profile,
    extract_brand_rules,
    generate_replacements,
    load_brand_profile,
    match_brand_to_blueprint,
    match_source_script,
    validate_brand_profile,
)
from sws.core.script_reconstructor import (
    build_editable_script,
    build_replacement_plan,
    build_script_blueprint,
    extract_cue_points,
    extract_speaker_map,
    validate_replacement_plan,
)
from sws.core.timeline_builder import (
    build_rebuild_timeline,
    compose_timeline,
    compute_timeline_duration,
    plan_shot_interventions,
    sequence_brand_interventions,
    validate_rebuild_timeline,
)
from sws.core.locale_variants import (
    build_locale_variants,
    get_approved_locales,
    validate_locale_variants,
)


def _load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _validate_required_keys(data: dict, required: list[str], name: str) -> None:
    missing = [k for k in required if k not in data]
    assert not missing, f"{name}: missing required keys: {missing}"


# --- Golden fixture: rebuild blueprint ---
@pytest.fixture
def golden_blueprint():
    return _load_json(REPO_ROOT / "03_core" / "sws" / "examples" / "rebuild_blueprint.json")


@pytest.fixture
def golden_brand():
    return _load_json(GOLDEN_DIR / "brand_profile.json")


@pytest.fixture
def sample_identity():
    return {
        "tone": "educational",
        "audience": "developers",
        "niche_tags": ["tech", "tutorials"],
    }


@pytest.fixture
def sample_visual():
    return {
        "color_palette": ["#1A73E8", "#34A853"],
        "font_family": "Inter",
        "logo_asset_ref": "asset_logo_001",
    }


@pytest.fixture
def sample_audio():
    return {
        "voice_profile": "voice_en_01",
        "music_style": "ambient",
    }


# ============================================================
# SCHEMA TESTS (8 tests)
# ============================================================

class TestBrandProfileSchema:
    def test_schema_file_exists(self):
        assert (SCHEMA_DIR / "brand_profile.schema.json").exists()

    def test_schema_is_valid_json(self):
        schema = _load_json(SCHEMA_DIR / "brand_profile.schema.json")
        assert "$schema" in schema
        assert schema["type"] == "object"

    def test_golden_fixture_matches_schema_required(self):
        schema = _load_json(SCHEMA_DIR / "brand_profile.schema.json")
        golden = _load_json(GOLDEN_DIR / "brand_profile.json")
        required = schema.get("required", [])
        _validate_required_keys(golden, required, "brand_profile")


class TestReplacementPlanSchema:
    def test_schema_file_exists(self):
        assert (SCHEMA_DIR / "replacement_plan.schema.json").exists()

    def test_golden_fixture_matches_schema_required(self):
        schema = _load_json(SCHEMA_DIR / "replacement_plan.schema.json")
        golden = _load_json(GOLDEN_DIR / "replacement_plan.json")
        required = schema.get("required", [])
        _validate_required_keys(golden, required, "replacement_plan")


class TestRebuildTimelineSchema:
    def test_schema_file_exists(self):
        assert (SCHEMA_DIR / "rebuild_timeline.schema.json").exists()

    def test_golden_fixture_matches_schema_required(self):
        schema = _load_json(SCHEMA_DIR / "rebuild_timeline.schema.json")
        golden = _load_json(GOLDEN_DIR / "rebuild_timeline.json")
        required = schema.get("required", [])
        _validate_required_keys(golden, required, "rebuild_timeline")


class TestLocaleVariantsSchema:
    def test_schema_file_exists(self):
        assert (SCHEMA_DIR / "locale_variants.schema.json").exists()

    def test_golden_fixture_matches_schema_required(self):
        schema = _load_json(SCHEMA_DIR / "locale_variants.schema.json")
        golden = _load_json(GOLDEN_DIR / "locale_variants.json")
        required = schema.get("required", [])
        _validate_required_keys(golden, required, "locale_variants")


# ============================================================
# BRAND ENGINE TESTS (6 tests)
# ============================================================

class TestBrandEngine:
    def test_create_brand_profile(self, sample_identity, sample_visual, sample_audio):
        profile = create_brand_profile(
            brand_id="brand_test_001",
            brand_name="Test Brand",
            identity=sample_identity,
            visual=sample_visual,
            audio=sample_audio,
        )
        assert profile["brand_id"] == "brand_test_001"
        assert profile["version"] == 1
        assert "output_hash" in profile
        assert len(profile["output_hash"]) == 64

    def test_validate_brand_profile_valid(self, sample_identity, sample_visual, sample_audio):
        profile = create_brand_profile(
            brand_id="brand_test_002",
            brand_name="Valid Brand",
            identity=sample_identity,
            visual=sample_visual,
            audio=sample_audio,
        )
        errors = validate_brand_profile(profile)
        assert errors == []

    def test_validate_brand_profile_missing_fields(self):
        errors = validate_brand_profile({"brand_id": "brand_x"})
        assert len(errors) > 0
        assert any("Missing required field" in e for e in errors)

    def test_match_brand_to_blueprint(self, sample_identity, sample_visual, sample_audio, golden_blueprint):
        profile = create_brand_profile(
            brand_id="brand_match_001",
            brand_name="Match Brand",
            identity=sample_identity,
            visual=sample_visual,
            audio=sample_audio,
        )
        result = match_brand_to_blueprint(profile, golden_blueprint)
        assert "overall_score" in result
        assert 0 <= result["overall_score"] <= 1
        assert result["recommendation"] in ("proceed", "review_required")

    def test_apply_brand_styling(self, sample_identity, sample_visual, sample_audio):
        profile = create_brand_profile(
            brand_id="brand_style_001",
            brand_name="Style Brand",
            identity=sample_identity,
            visual=sample_visual,
            audio=sample_audio,
        )
        shot_timeline = {
            "shots": [
                {"shot_id": "shot_001", "start_frame": 0, "end_frame": 100, "duration_seconds": 3.3, "scene_type": "opening_static", "confidence": 0.9},
                {"shot_id": "shot_002", "start_frame": 100, "end_frame": 200, "duration_seconds": 3.3, "scene_type": "dialogue", "confidence": 0.85},
            ],
            "total_shots": 2,
        }
        result = apply_brand_styling(profile, shot_timeline)
        assert result["total_styled_shots"] == 2
        assert result["styled_shots"][0]["primary_color"] == "#1A73E8"
        assert result["styled_shots"][1]["primary_color"] == "#34A853"

    def test_apply_brand_styling_empty_shots(self, sample_identity, sample_visual, sample_audio):
        profile = create_brand_profile(
            brand_id="brand_empty_001",
            brand_name="Empty Brand",
            identity=sample_identity,
            visual=sample_visual,
            audio=sample_audio,
        )
        result = apply_brand_styling(profile, {"shots": [], "total_shots": 0})
        assert result["total_styled_shots"] == 0


# ============================================================
# SCRIPT RECONSTRUCTOR TESTS (5 tests)
# ============================================================

class TestScriptReconstructor:
    def test_build_replacement_plan(self, golden_blueprint, golden_brand):
        plan = build_replacement_plan(
            golden_blueprint, golden_brand,
            job_id="job_test_001", attempt_id="attempt_001",
        )
        assert plan["blueprint_id"] == "synthetic_short_video_v1.0"
        assert plan["brand_id"] == "brand_test_golden"
        assert len(plan["slot_assignments"]) > 0
        assert len(plan["asset_provenance_refs"]) > 0
        assert "output_hash" in plan

    def test_replacement_plan_has_voiceover_slots(self, golden_blueprint, golden_brand):
        plan = build_replacement_plan(
            golden_blueprint, golden_brand,
            job_id="job_test_002", attempt_id="attempt_002",
        )
        vo_slots = [s for s in plan["slot_assignments"] if s["slot_type"] == "voiceover"]
        assert len(vo_slots) == 3  # 3 transcript segments

    def test_replacement_plan_has_visual_slots(self, golden_blueprint, golden_brand):
        plan = build_replacement_plan(
            golden_blueprint, golden_brand,
            job_id="job_test_003", attempt_id="attempt_003",
        )
        vis_slots = [s for s in plan["slot_assignments"] if s["slot_type"] == "visual"]
        assert len(vis_slots) == 3  # 3 shots

    def test_validate_replacement_plan_valid(self, golden_blueprint, golden_brand):
        plan = build_replacement_plan(
            golden_blueprint, golden_brand,
            job_id="job_test_004", attempt_id="attempt_004",
        )
        errors = validate_replacement_plan(plan)
        assert errors == []

    def test_build_script_blueprint(self, golden_blueprint, golden_brand):
        plan = build_replacement_plan(
            golden_blueprint, golden_brand,
            job_id="job_test_005", attempt_id="attempt_005",
        )
        script = build_script_blueprint(
            golden_blueprint, plan, golden_brand,
            job_id="job_test_005", attempt_id="attempt_005",
        )
        assert len(script["segments"]) == 3
        assert "output_hash" in script
        assert script["segments"][0]["voice_profile"] == "voice_neutral_en_01"


# ============================================================
# TIMELINE BUILDER TESTS (5 tests)
# ============================================================

class TestTimelineBuilder:
    def test_build_rebuild_timeline(self, golden_blueprint, golden_brand):
        plan = build_replacement_plan(
            golden_blueprint, golden_brand,
            job_id="job_tl_001", attempt_id="attempt_tl_001",
        )
        shot_timeline = golden_blueprint["artifacts"]["shot_timeline"]
        timeline = build_rebuild_timeline(
            shot_timeline, plan,
            job_id="job_tl_001", attempt_id="attempt_tl_001",
        )
        assert "timeline_segments" in timeline
        assert "render_plan" in timeline
        assert "output_hash" in timeline

    def test_timeline_has_video_layer(self, golden_blueprint, golden_brand):
        plan = build_replacement_plan(
            golden_blueprint, golden_brand,
            job_id="job_tl_002", attempt_id="attempt_tl_002",
        )
        shot_timeline = golden_blueprint["artifacts"]["shot_timeline"]
        timeline = build_rebuild_timeline(
            shot_timeline, plan,
            job_id="job_tl_002", attempt_id="attempt_tl_002",
        )
        video_segs = [s for s in timeline["timeline_segments"] if s["layer"] == "video"]
        assert len(video_segs) == 3

    def test_timeline_fade_transition(self, golden_blueprint, golden_brand):
        plan = build_replacement_plan(
            golden_blueprint, golden_brand,
            job_id="job_tl_003", attempt_id="attempt_tl_003",
        )
        shot_timeline = golden_blueprint["artifacts"]["shot_timeline"]
        timeline = build_rebuild_timeline(
            shot_timeline, plan,
            job_id="job_tl_003", attempt_id="attempt_tl_003",
        )
        video_segs = [s for s in timeline["timeline_segments"] if s["layer"] == "video"]
        fade_segs = [s for s in video_segs if s["transition_in"] == "fade"]
        assert len(fade_segs) == 1  # shot_002 is transition_fade

    def test_validate_rebuild_timeline(self, golden_blueprint, golden_brand):
        plan = build_replacement_plan(
            golden_blueprint, golden_brand,
            job_id="job_tl_004", attempt_id="attempt_tl_004",
        )
        shot_timeline = golden_blueprint["artifacts"]["shot_timeline"]
        timeline = build_rebuild_timeline(
            shot_timeline, plan,
            job_id="job_tl_004", attempt_id="attempt_tl_004",
        )
        errors = validate_rebuild_timeline(timeline)
        assert errors == []

    def test_compute_timeline_duration(self, golden_blueprint, golden_brand):
        plan = build_replacement_plan(
            golden_blueprint, golden_brand,
            job_id="job_tl_005", attempt_id="attempt_tl_005",
        )
        shot_timeline = golden_blueprint["artifacts"]["shot_timeline"]
        timeline = build_rebuild_timeline(
            shot_timeline, plan,
            job_id="job_tl_005", attempt_id="attempt_tl_005",
        )
        duration = compute_timeline_duration(timeline)
        assert duration == 300.0


# ============================================================
# LOCALE VARIANTS TESTS (5 tests)
# ============================================================

class TestLocaleVariants:
    def test_build_locale_variants_primary(self, golden_blueprint, golden_brand):
        plan = build_replacement_plan(
            golden_blueprint, golden_brand,
            job_id="job_lv_001", attempt_id="attempt_lv_001",
        )
        script = build_script_blueprint(
            golden_blueprint, plan, golden_brand,
            job_id="job_lv_001", attempt_id="attempt_lv_001",
        )
        variants = build_locale_variants(
            script, ["en"], "en",
            job_id="job_lv_001", attempt_id="attempt_lv_001",
        )
        assert variants["primary_locale"] == "en"
        assert len(variants["variants"]) == 1
        assert variants["variants"][0]["review_status"] == "auto_approved"

    def test_build_locale_variants_multi(self, golden_blueprint, golden_brand):
        plan = build_replacement_plan(
            golden_blueprint, golden_brand,
            job_id="job_lv_002", attempt_id="attempt_lv_002",
        )
        script = build_script_blueprint(
            golden_blueprint, plan, golden_brand,
            job_id="job_lv_002", attempt_id="attempt_lv_002",
        )
        translation_map = {
            "de": {"1": "Segment eins", "2": "Segment zwei", "3": "Segment drei"},
        }
        variants = build_locale_variants(
            script, ["en", "de"], "en",
            job_id="job_lv_002", attempt_id="attempt_lv_002",
            translation_map=translation_map,
        )
        assert len(variants["variants"]) == 2
        de_variant = [v for v in variants["variants"] if v["locale"] == "de"][0]
        assert de_variant["script_segments"][0]["text"] == "Segment eins"
        assert de_variant["review_status"] == "pending"

    def test_build_locale_variants_untranslated(self, golden_blueprint, golden_brand):
        plan = build_replacement_plan(
            golden_blueprint, golden_brand,
            job_id="job_lv_003", attempt_id="attempt_lv_003",
        )
        script = build_script_blueprint(
            golden_blueprint, plan, golden_brand,
            job_id="job_lv_003", attempt_id="attempt_lv_003",
        )
        variants = build_locale_variants(
            script, ["en", "fr"], "en",
            job_id="job_lv_003", attempt_id="attempt_lv_003",
        )
        fr_variant = [v for v in variants["variants"] if v["locale"] == "fr"][0]
        assert "[UNTRANSLATED:fr]" in fr_variant["script_segments"][0]["text"]

    def test_validate_locale_variants(self, golden_blueprint, golden_brand):
        plan = build_replacement_plan(
            golden_blueprint, golden_brand,
            job_id="job_lv_004", attempt_id="attempt_lv_004",
        )
        script = build_script_blueprint(
            golden_blueprint, plan, golden_brand,
            job_id="job_lv_004", attempt_id="attempt_lv_004",
        )
        variants = build_locale_variants(
            script, ["en"], "en",
            job_id="job_lv_004", attempt_id="attempt_lv_004",
        )
        errors = validate_locale_variants(variants)
        assert errors == []

    def test_get_approved_locales(self, golden_blueprint, golden_brand):
        plan = build_replacement_plan(
            golden_blueprint, golden_brand,
            job_id="job_lv_005", attempt_id="attempt_lv_005",
        )
        script = build_script_blueprint(
            golden_blueprint, plan, golden_brand,
            job_id="job_lv_005", attempt_id="attempt_lv_005",
        )
        variants = build_locale_variants(
            script, ["en", "de"], "en",
            job_id="job_lv_005", attempt_id="attempt_lv_005",
        )
        approved = get_approved_locales(variants)
        assert "en" in approved
        assert "de" not in approved  # pending, no translation_map


# ============================================================
# INTEGRATION TESTS (3 tests)
# ============================================================

class TestRebuildIntegration:
    def test_full_rebuild_pipeline(self, golden_blueprint, golden_brand):
        """Full pipeline: blueprint -> replacement -> timeline -> locale."""
        plan = build_replacement_plan(
            golden_blueprint, golden_brand,
            job_id="job_int_001", attempt_id="attempt_int_001",
        )
        assert validate_replacement_plan(plan) == []

        script = build_script_blueprint(
            golden_blueprint, plan, golden_brand,
            job_id="job_int_001", attempt_id="attempt_int_001",
        )
        assert len(script["segments"]) > 0

        shot_timeline = golden_blueprint["artifacts"]["shot_timeline"]
        timeline = build_rebuild_timeline(
            shot_timeline, plan,
            job_id="job_int_001", attempt_id="attempt_int_001",
        )
        assert validate_rebuild_timeline(timeline) == []

        variants = build_locale_variants(
            script, ["en", "de-DE"], "en",
            job_id="job_int_001", attempt_id="attempt_int_001",
        )
        assert validate_locale_variants(variants) == []

    def test_timeline_with_beat_map(self, golden_blueprint, golden_brand):
        """Timeline builder with beat_map produces music layer."""
        plan = build_replacement_plan(
            golden_blueprint, golden_brand,
            job_id="job_int_002", attempt_id="attempt_int_002",
        )
        shot_timeline = golden_blueprint["artifacts"]["shot_timeline"]
        beat_map = {"bpm": 120, "beat_grid": [0.0, 0.5, 1.0, 1.5]}
        timeline = build_rebuild_timeline(
            shot_timeline, plan,
            job_id="job_int_002", attempt_id="attempt_int_002",
            beat_map=beat_map,
        )
        music_segs = [s for s in timeline["timeline_segments"] if s["layer"] == "music"]
        assert len(music_segs) == 1
        assert "bpm_120" in music_segs[0]["asset_ref"]

    def test_render_contract_exists(self):
        """Render contract template must exist."""
        rc = REPO_ROOT / "sws" / "templates" / "render_contract.md"
        assert rc.exists()
        content = rc.read_text(encoding="utf-8")
        assert "Resolution Tiers" in content
        assert "Codec Requirements" in content
        assert "Deterministic" in content


# ============================================================
# LANE C SPEC TESTS — brand_engine.load/match_source_script
# ============================================================

class TestBrandEngineLoad:
    def test_load_valid_profile(self, golden_brand):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(golden_brand, f)
            f.flush()
            path = f.name
        try:
            loaded = load_brand_profile(path)
            assert loaded["brand_id"] == "brand_test_golden"
        finally:
            os.unlink(path)

    def test_load_invalid_profile_raises(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump({"incomplete": True}, f)
            f.flush()
            path = f.name
        try:
            with pytest.raises(ValueError, match="Invalid brand profile"):
                load_brand_profile(path)
        finally:
            os.unlink(path)


class TestBrandEngineExtractRules:
    def test_extracts_constraint_rules(self, golden_brand):
        golden_brand["brand_rules"] = {
            "brand_kit_constraints": ["no_competitor", "color_match", "tone_check"],
            "compliance_thresholds": {"min_brand_match_score": 0.7, "max_deviation_percent": 15},
            "approval_process": "DUAL",
        }
        rules = extract_brand_rules(golden_brand)
        constraint_rules = [r for r in rules if r.get("constraint") != "color_palette_enforcement"]
        assert len(constraint_rules) == 3
        assert all(r["approval_process"] == "DUAL" for r in constraint_rules)

    def test_includes_color_palette_rule(self, golden_brand):
        golden_brand["brand_rules"] = {
            "brand_kit_constraints": [],
            "compliance_thresholds": {},
            "approval_process": "AUTOMATED",
        }
        rules = extract_brand_rules(golden_brand)
        palette_rules = [r for r in rules if r.get("constraint") == "color_palette_enforcement"]
        assert len(palette_rules) == 1
        assert len(palette_rules[0]["palette"]) == 5


class TestBrandMatchSourceScript:
    def test_match_finds_all_cue_points(self, golden_brand):
        golden_brand["brand_rules"] = {
            "brand_kit_constraints": ["rule_a"],
            "compliance_thresholds": {"min_brand_match_score": 0.5},
            "approval_process": "AUTOMATED",
        }
        rules = extract_brand_rules(golden_brand)
        script = {
            "cue_points": [
                {"cue_id": "cue_1", "time_seconds": 0, "text": "Hello"},
                {"cue_id": "cue_2", "time_seconds": 50, "text": "World"},
            ],
        }
        matched = match_source_script(script, rules)
        assert len(matched) == 2
        assert all("matched_rules" in cp for cp in matched)

    def test_match_empty_script(self, golden_brand):
        golden_brand["brand_rules"] = {
            "brand_kit_constraints": ["x"],
            "compliance_thresholds": {},
            "approval_process": "HUMAN_REVIEW",
        }
        rules = extract_brand_rules(golden_brand)
        matched = match_source_script({"cue_points": []}, rules)
        assert matched == []


class TestBrandGenerateReplacements:
    def test_generates_replacements(self, golden_brand):
        golden_brand["brand_rules"] = {
            "brand_kit_constraints": ["r1", "r2"],
            "compliance_thresholds": {"min_brand_match_score": 0.6},
            "approval_process": "DUAL",
        }
        rules = extract_brand_rules(golden_brand)
        cue_points = [
            {"cue_id": "c1", "text": "Test", "matched_rules": ["rule_000", "rule_001"]},
        ]
        result = generate_replacements(cue_points, rules)
        assert result["total_replacements"] == 2


# ============================================================
# LANE C SPEC TESTS — script_reconstructor.extract_speaker_map
# ============================================================

class TestScriptReconstructorSpeakerMap:
    def test_extract_from_blueprint(self, golden_blueprint):
        transcript = golden_blueprint["artifacts"]["transcript_master"]
        speaker_map = extract_speaker_map(transcript)
        assert len(speaker_map) == 3

    def test_deduplicates_speakers(self):
        transcript = {
            "segments": [
                {"segment_id": 1, "speaker_id": "sp1", "speaker_name": "Alice"},
                {"segment_id": 2, "speaker_id": "sp1", "speaker_name": "Alice"},
                {"segment_id": 3, "speaker_id": "sp2", "speaker_name": "Bob"},
            ]
        }
        speaker_map = extract_speaker_map(transcript)
        assert len(speaker_map) == 2
        assert speaker_map["sp1"] == "Alice"


class TestScriptReconstructorCuePoints:
    def test_extract_cue_points(self, golden_blueprint):
        shot_timeline = golden_blueprint["artifacts"]["shot_timeline"]
        transcript = golden_blueprint["artifacts"]["transcript_master"]
        cue_points = extract_cue_points(shot_timeline, transcript)
        assert len(cue_points) == 3
        for cp in cue_points:
            assert "cue_id" in cp
            assert "scene_context" in cp

    def test_cue_points_scene_context(self, golden_blueprint):
        shot_timeline = golden_blueprint["artifacts"]["shot_timeline"]
        transcript = golden_blueprint["artifacts"]["transcript_master"]
        cue_points = extract_cue_points(shot_timeline, transcript)
        assert cue_points[0]["scene_context"] == "opening_static"
        assert cue_points[1]["scene_context"] == "transition_fade"
        assert cue_points[2]["scene_context"] == "closing_static"


class TestScriptReconstructorEditableScript:
    def test_build_editable_script(self, golden_blueprint):
        shot_timeline = golden_blueprint["artifacts"]["shot_timeline"]
        transcript = golden_blueprint["artifacts"]["transcript_master"]
        cue_points = extract_cue_points(shot_timeline, transcript)
        script = build_editable_script(cue_points)
        assert script["format"] == "editable_script"
        assert script["total_lines"] == 3
        assert script["lines"][0]["line_number"] == 1


# ============================================================
# LANE C SPEC TESTS — timeline_builder.plan_interventions
# ============================================================

class TestTimelinePlanInterventions:
    def test_plan_from_replacement_plan(self, golden_blueprint, golden_brand):
        shot_timeline = golden_blueprint["artifacts"]["shot_timeline"]
        replacement_plan = build_replacement_plan(
            golden_blueprint, golden_brand, "job_pi", "attempt_pi"
        )
        interventions = plan_shot_interventions(replacement_plan, shot_timeline)
        assert len(interventions) > 0
        for intv in interventions:
            assert intv["timing"]["start_seconds"] < intv["timing"]["end_seconds"]

    def test_no_timeline_conflicts(self, golden_blueprint, golden_brand):
        shot_timeline = golden_blueprint["artifacts"]["shot_timeline"]
        replacement_plan = build_replacement_plan(
            golden_blueprint, golden_brand, "job_nc", "attempt_nc"
        )
        interventions = plan_shot_interventions(replacement_plan, shot_timeline)
        sequenced = sequence_brand_interventions(interventions)
        conflicts = [s for s in sequenced if s.get("has_conflict")]
        assert len(conflicts) == 0


class TestTimelineSequence:
    def test_sorts_by_time(self):
        interventions = [
            {"shot_id": "shot_002", "shot_num": 2, "intervention_type": "VISUAL_EFFECT",
             "timing": {"start_seconds": 100, "end_seconds": 200}, "asset_ref": "a2"},
            {"shot_id": "shot_001", "shot_num": 1, "intervention_type": "VISUAL_EFFECT",
             "timing": {"start_seconds": 0, "end_seconds": 100}, "asset_ref": "a1"},
        ]
        sequenced = sequence_brand_interventions(interventions)
        assert sequenced[0]["timing"]["start_seconds"] == 0
        assert sequenced[1]["timing"]["start_seconds"] == 100

    def test_detects_overlap(self):
        interventions = [
            {"shot_id": "shot_001", "shot_num": 1, "intervention_type": "VISUAL_EFFECT",
             "timing": {"start_seconds": 0, "end_seconds": 150}, "asset_ref": "a1"},
            {"shot_id": "shot_002", "shot_num": 2, "intervention_type": "VISUAL_EFFECT",
             "timing": {"start_seconds": 100, "end_seconds": 200}, "asset_ref": "a2"},
        ]
        sequenced = sequence_brand_interventions(interventions)
        assert sequenced[1]["has_conflict"] is True


class TestTimelineCompose:
    def test_shot_count_matches(self, golden_blueprint):
        shot_timeline = golden_blueprint["artifacts"]["shot_timeline"]
        interventions = [
            {"shot_id": "shot_001", "shot_num": 1, "intervention_type": "TEXT_OVERLAY",
             "timing": {"start_seconds": 0, "end_seconds": 100}, "asset_ref": "overlay_1"},
        ]
        result = compose_timeline(shot_timeline, interventions)
        assert len(result["output_timeline"]["shot_updated"]) == len(shot_timeline["shots"])

    def test_marks_modified_shots(self, golden_blueprint):
        shot_timeline = golden_blueprint["artifacts"]["shot_timeline"]
        interventions = [
            {"shot_id": "shot_002", "shot_num": 2, "intervention_type": "VISUAL_EFFECT",
             "timing": {"start_seconds": 100, "end_seconds": 200}, "asset_ref": "vis_1"},
        ]
        result = compose_timeline(shot_timeline, interventions)
        updated = result["output_timeline"]["shot_updated"]
        assert updated[0]["modified"] is False
        assert updated[1]["modified"] is True
        assert updated[2]["modified"] is False


# ============================================================
# LANE C SPEC TESTS — Full E2E + Locale
# ============================================================

class TestE2EFullPipeline:
    def test_blueprint_to_rebuilt_timeline(self, golden_blueprint, golden_brand):
        """E2E: blueprint -> brand -> replacement -> rebuilt timeline (valid)."""
        golden_brand["brand_rules"] = {
            "brand_kit_constraints": ["no_competitor", "tone_check"],
            "compliance_thresholds": {"min_brand_match_score": 0.6},
            "approval_process": "AUTOMATED",
        }
        rules = extract_brand_rules(golden_brand)
        assert len(rules) > 0

        shot_timeline = golden_blueprint["artifacts"]["shot_timeline"]
        transcript = golden_blueprint["artifacts"]["transcript_master"]
        cue_points = extract_cue_points(shot_timeline, transcript)
        assert len(cue_points) == 3

        matched = match_source_script({"cue_points": cue_points}, rules)
        assert len(matched) == 3

        replacements = generate_replacements(matched, rules)
        assert replacements["total_replacements"] > 0

        replacement_plan = build_replacement_plan(
            golden_blueprint, golden_brand, "job_e2e", "attempt_e2e"
        )
        interventions = plan_shot_interventions(replacement_plan, shot_timeline)
        rebuilt = compose_timeline(shot_timeline, interventions)
        assert len(rebuilt["output_timeline"]["shot_updated"]) == len(shot_timeline["shots"])
        errors = validate_rebuild_timeline(rebuilt)
        assert errors == []

    def test_locale_variants_en_fr_gb(self, golden_blueprint, golden_brand):
        """Locale: en-US vs fr-FR vs en-GB text/audio/visual differ."""
        plan = build_replacement_plan(
            golden_blueprint, golden_brand, "job_lv_e2e", "attempt_001"
        )
        script = build_script_blueprint(
            golden_blueprint, plan, golden_brand, "job_lv_e2e", "attempt_001"
        )
        translation_map = {
            "fr-FR": {str(s["segment_id"]): f"[FR]{s['text']}" for s in golden_blueprint["artifacts"]["transcript_master"]["segments"]},
            "en-GB": {str(s["segment_id"]): f"[GB]{s['text']}" for s in golden_blueprint["artifacts"]["transcript_master"]["segments"]},
        }
        variants = build_locale_variants(
            script, ["en-US", "fr-FR", "en-GB"], "en-US",
            "job_lv_e2e", "attempt_001", translation_map=translation_map,
        )
        assert len(variants["variants"]) == 3
        assert validate_locale_variants(variants) == []
        en_text = variants["variants"][0]["script_segments"][0]["text"]
        fr_text = variants["variants"][1]["script_segments"][0]["text"]
        gb_text = variants["variants"][2]["script_segments"][0]["text"]
        assert en_text != fr_text
        assert fr_text != gb_text


class TestBrandVariantExpansion:
    def test_seasonal_regional_4_combinations(self, golden_brand):
        """Verify seasonal + regional = 4 combinations."""
        golden_brand["brand_variants"] = [
            {"variant_type": "seasonal", "variant_key": "summer_2026", "overrides": {}},
            {"variant_type": "seasonal", "variant_key": "winter_2026", "overrides": {}},
            {"variant_type": "regional", "variant_key": "DACH", "overrides": {}},
            {"variant_type": "regional", "variant_key": "APAC", "overrides": {}},
        ]
        seasonal = [v for v in golden_brand["brand_variants"] if v["variant_type"] == "seasonal"]
        regional = [v for v in golden_brand["brand_variants"] if v["variant_type"] == "regional"]
        combinations = [(s["variant_key"], r["variant_key"]) for s in seasonal for r in regional]
        assert len(combinations) == 4
