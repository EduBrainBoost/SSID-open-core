import json
import math
import subprocess
from pathlib import Path

SSID_ROOT = Path(__file__).parent.parent.parent.parent
FEE_SCRIPT = SSID_ROOT / "23_compliance" / "scripts" / "fee_policy_audit.py"
SUB_SCRIPT = SSID_ROOT / "23_compliance" / "scripts" / "subscription_audit.py"
POFI_SCRIPT = SSID_ROOT / "23_compliance" / "scripts" / "pofi_formula_check.py"
DAO_SCRIPT = SSID_ROOT / "23_compliance" / "scripts" / "dao_params_check.py"
FEE_POLICY = SSID_ROOT / "23_compliance" / "fee_allocation_policy.yaml"
SUB_POLICY = SSID_ROOT / "07_governance_legal" / "subscription_revenue_policy.yaml"
POFI_POLICY = SSID_ROOT / "07_governance_legal" / "proof_of_fairness_policy.yaml"


def test_7_saeulen_sum_exactly_2_percent(tmp_path):
    """7-Säulen fee distribution must sum to exactly 2.00%."""
    out = tmp_path / "fee_check.json"
    r = subprocess.run(
        ["python", str(FEE_SCRIPT),
         "--policy", str(FEE_POLICY),
         "--out", str(out)],
        capture_output=True, text=True
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(out.read_text())
    assert data["status"] == "PASS"
    assert abs(data["total_percent"] - 2.00) < 0.001
    assert data["pillar_count"] == 7


def test_subscription_50_30_10_10_model(tmp_path):
    """Subscription distribution must follow 50/30/10/10 model summing to 100%."""
    out = tmp_path / "sub_audit.json"
    r = subprocess.run(
        ["python", str(SUB_SCRIPT),
         "--policy", str(SUB_POLICY),
         "--out", str(out)],
        capture_output=True, text=True
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(out.read_text())
    assert data["status"] == "PASS"
    assert data["total_percent"] == 100
    assert data["distribution"]["protocol_development"] == 50
    assert data["distribution"]["community_rewards"] == 30
    assert data["distribution"]["dao_governance"] == 10
    assert data["distribution"]["operational_reserve"] == 10


def test_pofi_formula_matches_sot(tmp_path):
    """POFI formula: log(activity+1)/log(rewards+10) must pass reference tests."""
    out = tmp_path / "pofi_check.json"
    r = subprocess.run(
        ["python", str(POFI_SCRIPT),
         "--policy", str(POFI_POLICY),
         "--out", str(out)],
        capture_output=True, text=True
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(out.read_text())
    assert data["status"] == "PASS"
    assert data["monotone_check"] is True

    # Verify specific formula values
    def pofi(a, r_val):
        return math.log(a + 1) / math.log(r_val + 10)

    assert abs(pofi(0, 0) - 0.0) < 1e-9       # zero activity = 0
    assert abs(pofi(9, 0) - 1.0) < 1e-9       # activity=9, rewards=0 = exactly 1.0


def test_dao_params_within_governance_ranges(tmp_path):
    """DAO default parameters must all be within their defined policy ranges."""
    out = tmp_path / "dao_params.json"
    r = subprocess.run(
        ["python", str(DAO_SCRIPT),
         "--policy", str(SUB_POLICY),
         "--out", str(out)],
        capture_output=True, text=True
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(out.read_text())
    assert data["status"] == "PASS", f"DAO param failures: {data.get('failures')}"
    assert data["failures"] == []


def test_quarterly_guard_correct(tmp_path):
    """Fee policy must include quarterly guard metadata."""
    import yaml
    pofi = yaml.safe_load(POFI_POLICY.read_text())
    qa = pofi.get("quarterly_audit", {})
    assert qa.get("required") is True
    assert "quarter_key" in qa.get("guard_field", "")


def test_fee_policy_fail_if_wrong_sum(tmp_path):
    """A policy with wrong sum must return FAIL_POLICY."""
    bad_policy = tmp_path / "bad_fee_policy.yaml"
    bad_policy.write_text(
        "version: '0.0'\npillars:\n"
        "  p1:\n    percent: 0.50\n    label: A\n    destination: x\n"
        "  p2:\n    percent: 0.50\n    label: B\n    destination: y\n"
        "  p3:\n    percent: 0.50\n    label: C\n    destination: z\n"
        "  p4:\n    percent: 0.50\n    label: D\n    destination: w\n"
        "  p5:\n    percent: 0.50\n    label: E\n    destination: v\n"
        "  p6:\n    percent: 0.50\n    label: F\n    destination: u\n"
        "  p7:\n    percent: 0.50\n    label: G\n    destination: t\n"
        "sum_tolerance: 0.001\n"
    )
    out = tmp_path / "bad_result.json"
    r = subprocess.run(
        ["python", str(FEE_SCRIPT),
         "--policy", str(bad_policy),
         "--out", str(out)],
        capture_output=True, text=True
    )
    assert r.returncode == 1
    data = json.loads(out.read_text())
    assert data["status"] == "FAIL_POLICY"
