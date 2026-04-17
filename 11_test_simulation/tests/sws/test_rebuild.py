"""
Tests for SWS Rebuild Render — Lane C.

Covers: brand_engine, script_reconstructor, timeline_builder,
locale_variants, schemas, and integration flows.

Target: 30+ tests.
"""

import json
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
    create_brand_profile,
    match_brand_to_blueprint,
    validate_brand_profile,
)
from sws.core.script_reconstructor import (
    build_replacement_plan,
    build_script_blueprint,
    validate_replacement_plan,
)
from sws.core.timeline_builder import (
    build_rebuild_timeline,
    compute_timeline_duration,
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
