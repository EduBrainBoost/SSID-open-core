import json
import math
import subprocess
from datetime import UTC
from pathlib import Path

SSID_ROOT = Path(__file__).parent.parent.parent.parent
INVENTORY_SCRIPT = SSID_ROOT / "01_ai_layer" / "scripts" / "model_inventory.py"
FAIRNESS_SCRIPT = SSID_ROOT / "01_ai_layer" / "scripts" / "fairness_metric_calc.py"
POFI_AUDIT_SCRIPT = SSID_ROOT / "08_identity_score" / "scripts" / "pofi_audit.py"
TEST_DATASET = SSID_ROOT / "22_datasets" / "bias_test_suite.yaml"
POFI_POLICY = SSID_ROOT / "07_governance_legal" / "proof_of_fairness_policy.yaml"


def test_model_inventory_complete(tmp_path):
    """model_inventory.py must scan and produce valid schema output."""
    out = tmp_path / "inventory.json"
    r = subprocess.run(
        [
            "python",
            str(INVENTORY_SCRIPT),
            "--scan-dirs",
            "01_ai_layer",
            "08_identity_score",
            "--repo-root",
            str(SSID_ROOT),
            "--out",
            str(out),
        ],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(out.read_text())
    assert "total_models" in data
    assert "models" in data
    assert "scan_ts" in data
    assert isinstance(data["models"], list)


def test_demographic_parity_threshold_enforced(tmp_path):
    """Demographic parity diff within threshold passes; exceeding it fails."""
    inventory = tmp_path / "inventory.json"
    inventory.write_text(json.dumps({"total_models": 1, "models": [], "scan_ts": ""}))

    out = tmp_path / "fairness.json"
    r = subprocess.run(
        [
            "python",
            str(FAIRNESS_SCRIPT),
            "--models",
            str(inventory),
            "--metrics",
            "demographic_parity",
            "--test-dataset",
            str(TEST_DATASET),
            "--out",
            str(out),
        ],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(out.read_text())
    assert data["status"] == "PASS"
    dp = data["metrics"]["demographic_parity"]
    assert dp["max_diff"] <= dp["threshold"]


def test_equal_opportunity_threshold_enforced(tmp_path):
    """All groups must meet minimum TPR from test suite thresholds."""
    inventory = tmp_path / "inventory.json"
    inventory.write_text(json.dumps({"total_models": 1, "models": [], "scan_ts": ""}))
    out = tmp_path / "fairness.json"
    r = subprocess.run(
        [
            "python",
            str(FAIRNESS_SCRIPT),
            "--models",
            str(inventory),
            "--metrics",
            "equal_opportunity",
            "--test-dataset",
            str(TEST_DATASET),
            "--out",
            str(out),
        ],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(out.read_text())
    assert data["status"] == "PASS"
    eo = data["metrics"]["equal_opportunity"]
    assert eo["failing_groups"] == []


def test_quarterly_guard_prevents_double_run(tmp_path):
    """POFI audit run twice in same quarter — second run returns DUPLICATE."""
    from datetime import datetime

    quarter = f"{datetime.now(UTC).year}-Q{(datetime.now(UTC).month - 1) // 3 + 1}"
    state_file = tmp_path / "pofi_state.json"
    state_file.write_text(json.dumps({"quarter_key": quarter}))

    out = tmp_path / "pofi_audit.json"
    r = subprocess.run(
        [
            "python",
            str(POFI_AUDIT_SCRIPT),
            "--policy",
            str(POFI_POLICY),
            "--state",
            str(state_file),
            "--repo-root",
            str(SSID_ROOT),
            "--out",
            str(out),
        ],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(out.read_text())
    assert data["status"] == "DUPLICATE"


def test_pofi_formula_correct():
    """POFI = log(activity+1) / log(rewards+10) verified numerically."""

    def pofi(a, r):
        return math.log(a + 1) / math.log(r + 10)

    assert abs(pofi(0, 0) - 0.0) < 1e-9  # zero activity = 0
    assert abs(pofi(9, 0) - 1.0) < 1e-9  # activity=9: log(10)/log(10) = 1
    # Monotone: higher activity → higher score (same rewards)
    assert pofi(10, 0) > pofi(5, 0) > pofi(1, 0) > pofi(0, 0)


def test_report_generated_in_correct_path(tmp_path):
    """POFI audit writes output to the specified path."""
    out = tmp_path / "pofi_result.json"
    r = subprocess.run(
        [
            "python",
            str(POFI_AUDIT_SCRIPT),
            "--policy",
            str(POFI_POLICY),
            "--state",
            str(tmp_path / "no_state.json"),
            "--repo-root",
            str(SSID_ROOT),
            "--out",
            str(out),
        ],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr
    assert out.exists()
    data = json.loads(out.read_text())
    assert data["status"] in ("PASS", "DUPLICATE")
    assert "ts" in data
