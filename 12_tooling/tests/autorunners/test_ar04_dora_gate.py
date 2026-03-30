import json
import subprocess
from pathlib import Path

SSID_ROOT = Path(__file__).parent.parent.parent.parent
CHECK_SCRIPT = SSID_ROOT / "23_compliance" / "scripts" / "dora_incident_plan_check.py"
VALIDATE_SCRIPT = SSID_ROOT / "23_compliance" / "scripts" / "dora_content_validate.py"


def test_all_24_roots_checked(tmp_path):
    """Script must check exactly 24 roots in its default run."""
    out = tmp_path / "dora_check.json"
    r = subprocess.run(
        ["python", str(CHECK_SCRIPT),
         "--repo-root", str(SSID_ROOT),
         "--out", str(out)],
        capture_output=True, text=True
    )
    # May exit 1 (some roots missing IRP) — schema must still be valid
    assert r.returncode in (0, 1), r.stderr
    data = json.loads(out.read_text())
    assert data["total_roots"] == 24
    assert "missing" in data
    assert "checks" in data
    assert len(data["checks"]) == 24


def test_missing_plan_detected(tmp_path):
    """Root without incident_response_plan.md is reported as missing."""
    root_dir = tmp_path / "01_ai_layer"
    root_dir.mkdir(parents=True)
    # No docs/incident_response_plan.md created
    out = tmp_path / "dora.json"
    r = subprocess.run(
        ["python", str(CHECK_SCRIPT),
         "--repo-root", str(tmp_path),
         "--roots", "01_ai_layer",
         "--out", str(out)],
        capture_output=True, text=True
    )
    assert r.returncode == 1  # FAIL_DORA
    data = json.loads(out.read_text())
    assert "01_ai_layer" in data["missing"]
    assert data["status"] == "FAIL_DORA"


def test_existing_plan_not_overwritten(tmp_path):
    """Present plan is reported as compliant, not in missing list."""
    root_dir = tmp_path / "03_core" / "docs"
    root_dir.mkdir(parents=True)
    plan = root_dir / "incident_response_plan.md"
    plan.write_text("# IRP\n## Section 1\n## Section 2\n## Section 3\n## Section 4\n## Section 5\n")
    out = tmp_path / "dora.json"
    r = subprocess.run(
        ["python", str(CHECK_SCRIPT),
         "--repo-root", str(tmp_path),
         "--roots", "03_core",
         "--out", str(out)],
        capture_output=True, text=True
    )
    assert r.returncode == 0
    data = json.loads(out.read_text())
    assert "03_core" not in data["missing"]
    assert data["compliant"] == 1
    assert data["status"] == "PASS"


def test_empty_plan_triggers_fail_policy(tmp_path):
    """Present but empty plan fails content validation."""
    root_dir = tmp_path / "02_audit_logging" / "docs"
    root_dir.mkdir(parents=True)
    (root_dir / "incident_response_plan.md").write_text("")  # empty
    out_check = tmp_path / "check.json"
    subprocess.run(
        ["python", str(CHECK_SCRIPT),
         "--repo-root", str(tmp_path),
         "--roots", "02_audit_logging",
         "--out", str(out_check)],
        capture_output=True, text=True
    )
    out_val = tmp_path / "validation.json"
    r = subprocess.run(
        ["python", str(VALIDATE_SCRIPT),
         "--results", str(out_check),
         "--min-sections", "5",
         "--repo-root", str(tmp_path),
         "--out", str(out_val)],
        capture_output=True, text=True
    )
    assert r.returncode == 1  # FAIL_POLICY
    data = json.loads(out_val.read_text())
    assert data["status"] == "FAIL_POLICY"
    assert "02_audit_logging" in data["fail_policy_roots"]


def test_template_has_required_sections():
    """Template must have at least 5 sections (our own quality gate)."""
    template = SSID_ROOT / "05_documentation" / "templates" / "TEMPLATE_INCIDENT_RESPONSE.md"
    assert template.exists(), "Template must exist"
    content = template.read_text()
    sections = [ln for ln in content.splitlines() if ln.startswith("#")]
    assert len(sections) >= 5, f"Template needs >= 5 sections, found {len(sections)}"
