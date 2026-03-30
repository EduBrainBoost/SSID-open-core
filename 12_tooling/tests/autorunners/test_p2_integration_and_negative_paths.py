"""P2 Gate: Integration + Negative-Path tests for AR-01/03/04/06/09/10.

These tests verify:
1. Each module runs against REAL SSID repo data (integration proof)
2. Each module produces a real FAIL/DENY on bad inputs (negative path)

Hard rules enforced:
- No fake pass: every PASS test checks actual result field
- No stub: FAIL tests verify exit code AND status field
"""
import hashlib
import json
import subprocess
from pathlib import Path

SSID_ROOT = Path(__file__).parent.parent.parent.parent

# Script paths
AR01_SCAN = SSID_ROOT / "23_compliance" / "scripts" / "pii_regex_scan.py"
AR01_PATTERNS = SSID_ROOT / "23_compliance" / "rules" / "pii_patterns.yaml"
AR03_COLLECT = SSID_ROOT / "02_audit_logging" / "scripts" / "collect_unanchored.py"
AR03_MERKLE = SSID_ROOT / "02_audit_logging" / "scripts" / "build_merkle_tree.py"
AR04_CHECK = SSID_ROOT / "23_compliance" / "scripts" / "dora_incident_plan_check.py"
AR04_VALIDATE = SSID_ROOT / "23_compliance" / "scripts" / "dora_content_validate.py"
AR06_GEN = SSID_ROOT / "05_documentation" / "scripts" / "generate_from_chart.py"
AR06_TEMPLATE = SSID_ROOT / "05_documentation" / "templates" / "chart_to_markdown.j2"
AR09_FAIRNESS = SSID_ROOT / "01_ai_layer" / "scripts" / "fairness_metric_calc.py"
AR09_POFI = SSID_ROOT / "08_identity_score" / "scripts" / "pofi_audit.py"
AR10_FEE = SSID_ROOT / "23_compliance" / "scripts" / "fee_policy_audit.py"
AR10_SUB = SSID_ROOT / "23_compliance" / "scripts" / "subscription_audit.py"
AR10_POFI = SSID_ROOT / "23_compliance" / "scripts" / "pofi_formula_check.py"
AR10_DAO = SSID_ROOT / "23_compliance" / "scripts" / "dao_params_check.py"


# ---------------------------------------------------------------------------
# AR-01 PII Scanner
# ---------------------------------------------------------------------------

class TestAR01Integration:
    def test_real_repo_python_files_pass(self, tmp_path):
        """Real SSID Python files in 12_tooling/ssid_autorunner/ must pass PII scan."""
        target_dir = SSID_ROOT / "12_tooling" / "ssid_autorunner"
        py_files = list(target_dir.glob("*.py"))
        assert py_files, "Expected Python files in ssid_autorunner/"
        out = tmp_path / "pii.json"
        r = subprocess.run(
            ["python", str(AR01_SCAN),
             "--files"] + [str(f) for f in py_files] + [
             "--patterns", str(AR01_PATTERNS),
             "--out", str(out)],
            capture_output=True, text=True
        )
        assert r.returncode == 0, f"Real SSID code failed PII scan: {r.stdout}"
        data = json.loads(out.read_text())
        assert data["status"] == "PASS"
        assert data["total_files_scanned"] == len(py_files)

    def test_iban_in_file_triggers_fail(self, tmp_path):
        """File containing a real IBAN triggers FAIL_POLICY (DENY path)."""
        dirty = tmp_path / "payment.py"
        # Real IBAN format: DE89 3704 0044 0532 0130 00
        dirty.write_text('BANK_ACCOUNT = "DE89370400440532013000"\n')
        out = tmp_path / "pii.json"
        r = subprocess.run(
            ["python", str(AR01_SCAN),
             "--files", str(dirty),
             "--patterns", str(AR01_PATTERNS),
             "--out", str(out)],
            capture_output=True, text=True
        )
        assert r.returncode == 1, "IBAN in code must FAIL (DENY path)"
        data = json.loads(out.read_text())
        assert data["status"] == "FAIL_POLICY"
        assert data["total_findings"] > 0

    def test_output_never_stores_pii_value(self, tmp_path):
        """Evidence output must NOT contain the actual email string."""
        dirty = tmp_path / "leak.py"
        dirty.write_text('ADMIN_MAIL = "admin.secret@corp-internal.de"\n')
        out = tmp_path / "pii.json"
        subprocess.run(
            ["python", str(AR01_SCAN),
             "--files", str(dirty),
             "--patterns", str(AR01_PATTERNS),
             "--out", str(out)],
            capture_output=True, text=True
        )
        content = out.read_text()
        assert "admin.secret@corp-internal.de" not in content, \
            "PII value must never appear in scan output"


# ---------------------------------------------------------------------------
# AR-03 Evidence Anchoring
# ---------------------------------------------------------------------------

class TestAR03Integration:
    def test_real_agent_runs_collection(self, tmp_path):
        """Collecting from real SSID agent_runs produces valid output."""
        real_runs = SSID_ROOT / "02_audit_logging" / "agent_runs"
        state = tmp_path / "anchor_state.json"
        out = tmp_path / "unanchored.json"
        r = subprocess.run(
            ["python", str(AR03_COLLECT),
             "--since-last-anchor", str(state),
             "--agent-runs-dir", str(real_runs),
             "--out", str(out)],
            capture_output=True, text=True
        )
        assert r.returncode == 0, r.stderr
        data = json.loads(out.read_text())
        assert "total_unanchored" in data
        assert "entries" in data
        # May be 0 or more — both valid. What matters: schema is correct.
        assert isinstance(data["total_unanchored"], int)

    def test_merkle_empty_queue_produces_dry_run(self, tmp_path):
        """Empty queue → Merkle root is None (dry_run, no anchor submitted)."""
        empty_input = tmp_path / "empty.json"
        empty_input.write_text(json.dumps({"total_unanchored": 0, "entries": []}))
        out = tmp_path / "merkle.json"
        r = subprocess.run(
            ["python", str(AR03_MERKLE),
             "--input", str(empty_input),
             "--out", str(out)],
            capture_output=True, text=True
        )
        assert r.returncode == 0, r.stderr
        data = json.loads(out.read_text())
        assert data["empty"] is True
        assert data["root"] is None, "Empty queue must NOT produce a Merkle root"

    def test_already_anchored_files_not_recollected(self, tmp_path):
        """Files in anchor_state.anchored_hashes are NOT re-collected (DENY duplicate)."""
        agent_runs = tmp_path / "agent_runs"
        agent_runs.mkdir()
        run_dir = agent_runs / "run-already-done"
        run_dir.mkdir()
        ev = run_dir / "evidence.jsonl"
        ev.write_text('{"check":"contract","result":"PASS"}\n')
        file_hash = hashlib.sha256(ev.read_bytes()).hexdigest()

        state = tmp_path / "state.json"
        state.write_text(json.dumps({"anchored_hashes": [file_hash]}))

        out = tmp_path / "result.json"
        subprocess.run(
            ["python", str(AR03_COLLECT),
             "--since-last-anchor", str(state),
             "--agent-runs-dir", str(agent_runs),
             "--out", str(out)],
            check=True
        )
        data = json.loads(out.read_text())
        assert data["total_unanchored"] == 0, \
            "Already-anchored files must be blocked (DENY duplicate)"


# ---------------------------------------------------------------------------
# AR-04 DORA Incident Plan Gate
# ---------------------------------------------------------------------------

class TestAR04Integration:
    def test_real_24_roots_checked(self, tmp_path):
        """Real SSID repo: all 24 roots are checked. Some may fail — schema must hold."""
        out = tmp_path / "dora.json"
        r = subprocess.run(
            ["python", str(AR04_CHECK),
             "--repo-root", str(SSID_ROOT),
             "--out", str(out)],
            capture_output=True, text=True
        )
        # exit 0 (all compliant) or 1 (some missing) — both valid real outcomes
        assert r.returncode in (0, 1), r.stderr
        data = json.loads(out.read_text())
        assert data["total_roots"] == 24
        assert len(data["checks"]) == 24
        assert "missing" in data
        assert "compliant" in data

    def test_incomplete_dora_plan_blocked(self, tmp_path):
        """Root with < 5 sections in IRP triggers FAIL_POLICY (DENY path)."""
        root_dir = tmp_path / "01_ai_layer" / "docs"
        root_dir.mkdir(parents=True)
        # Only 2 sections — insufficient
        (root_dir / "incident_response_plan.md").write_text(
            "# IRP\n## Section 1 — Purpose\n"
        )
        out_check = tmp_path / "check.json"
        subprocess.run(
            ["python", str(AR04_CHECK),
             "--repo-root", str(tmp_path),
             "--roots", "01_ai_layer",
             "--out", str(out_check)],
            capture_output=True, text=True
        )
        out_val = tmp_path / "val.json"
        r = subprocess.run(
            ["python", str(AR04_VALIDATE),
             "--results", str(out_check),
             "--min-sections", "5",
             "--repo-root", str(tmp_path),
             "--out", str(out_val)],
            capture_output=True, text=True
        )
        assert r.returncode == 1, "Thin IRP must FAIL_POLICY (DENY path)"
        data = json.loads(out_val.read_text())
        assert data["status"] == "FAIL_POLICY"
        assert "01_ai_layer" in data["fail_policy_roots"]

    def test_missing_root_triggers_fail_dora(self, tmp_path):
        """Root without any IRP: exit 1, status FAIL_DORA."""
        (tmp_path / "03_core").mkdir()
        out = tmp_path / "dora.json"
        r = subprocess.run(
            ["python", str(AR04_CHECK),
             "--repo-root", str(tmp_path),
             "--roots", "03_core",
             "--out", str(out)],
            capture_output=True, text=True
        )
        assert r.returncode == 1
        data = json.loads(out.read_text())
        assert data["status"] == "FAIL_DORA"
        assert "03_core" in data["missing"]


# ---------------------------------------------------------------------------
# AR-06 Doc Generation
# ---------------------------------------------------------------------------

class TestAR06Integration:
    def test_real_module_yamls_render_correctly(self, tmp_path):
        """Multiple real module.yaml files render to non-empty Markdown."""
        charts = [
            SSID_ROOT / "12_tooling" / "module.yaml",
            SSID_ROOT / "23_compliance" / "module.yaml",
        ]
        charts = [c for c in charts if c.exists()]
        assert charts, "Need at least one real module.yaml"

        chart_list = tmp_path / "charts.txt"
        chart_list.write_text("\n".join(str(c) for c in charts))
        out_dir = tmp_path / "generated"
        manifest = tmp_path / "manifest.json"

        r = subprocess.run(
            ["python", str(AR06_GEN),
             "--charts", str(chart_list),
             "--template", str(AR06_TEMPLATE),
             "--out-dir", str(out_dir),
             "--out-manifest", str(manifest),
             "--repo-root", str(SSID_ROOT)],
            capture_output=True, text=True
        )
        assert r.returncode == 0, r.stderr
        data = json.loads(manifest.read_text())
        assert data["status"] == "PASS"
        for entry in data["generated"]:
            doc = Path(entry["output"])
            assert doc.exists()
            assert len(doc.read_text().strip()) > 50, \
                f"Generated doc {doc} is too short (empty or near-empty)"

    def test_empty_charts_list_returns_pass_no_generate(self, tmp_path):
        """Empty charts list: PASS with 0 generated (not blocked, not errored)."""
        chart_list = tmp_path / "charts.txt"
        chart_list.write_text("")
        manifest = tmp_path / "manifest.json"
        r = subprocess.run(
            ["python", str(AR06_GEN),
             "--charts", str(chart_list),
             "--template", str(AR06_TEMPLATE),
             "--out-dir", str(tmp_path / "gen"),
             "--out-manifest", str(manifest),
             "--repo-root", str(SSID_ROOT)],
            capture_output=True, text=True
        )
        assert r.returncode == 0
        data = json.loads(manifest.read_text())
        assert data["total_charts"] == 0
        assert data["status"] == "PASS"

    def test_nonexistent_chart_does_not_crash(self, tmp_path):
        """Non-existent chart path is silently skipped (treated as 0 charts)."""
        chart_list = tmp_path / "charts.txt"
        chart_list.write_text("/nonexistent/path/chart.yaml\n")
        manifest = tmp_path / "manifest.json"
        r = subprocess.run(
            ["python", str(AR06_GEN),
             "--charts", str(chart_list),
             "--template", str(AR06_TEMPLATE),
             "--out-dir", str(tmp_path / "gen"),
             "--out-manifest", str(manifest),
             "--repo-root", str(SSID_ROOT)],
            capture_output=True, text=True
        )
        assert r.returncode == 0


# ---------------------------------------------------------------------------
# AR-09 Bias/Fairness Audit
# ---------------------------------------------------------------------------

class TestAR09Integration:
    def test_real_model_inventory_scans_ssid(self, tmp_path):
        """Real SSID model inventory scan returns valid schema."""
        out = tmp_path / "inventory.json"
        r = subprocess.run(
            ["python", str(SSID_ROOT / "01_ai_layer" / "scripts" / "model_inventory.py"),
             "--scan-dirs", "01_ai_layer", "08_identity_score",
             "--repo-root", str(SSID_ROOT),
             "--out", str(out)],
            capture_output=True, text=True
        )
        assert r.returncode == 0, r.stderr
        data = json.loads(out.read_text())
        assert "total_models" in data
        assert "scan_ts" in data
        assert isinstance(data["models"], list)

    def test_demographic_parity_violation_triggers_fail(self, tmp_path):
        """Bias threshold exceeded → FAIL_POLICY (DENY path)."""
        import yaml
        # Craft a test suite with a parity diff > 0.05
        bad_suite = {
            "test_vectors": {
                "demographic_parity": [
                    {"group": "group_a", "expected_positive_rate": 0.80, "tolerance": 0.01},
                    {"group": "group_b", "expected_positive_rate": 0.50, "tolerance": 0.01},
                ]
            },
            "thresholds": {
                "demographic_parity_max_diff": 0.05,
                "equal_opportunity_min": 0.95,
            }
        }
        bad_yaml = tmp_path / "bad_suite.yaml"
        bad_yaml.write_text(yaml.dump(bad_suite))
        inventory = tmp_path / "inv.json"
        inventory.write_text(json.dumps({"total_models": 1, "models": [], "scan_ts": ""}))
        out = tmp_path / "fairness.json"
        r = subprocess.run(
            ["python", str(AR09_FAIRNESS),
             "--models", str(inventory),
             "--metrics", "demographic_parity",
             "--test-dataset", str(bad_yaml),
             "--out", str(out)],
            capture_output=True, text=True
        )
        assert r.returncode == 1, "Bias violation must exit 1 (DENY path)"
        data = json.loads(out.read_text())
        assert data["status"] == "FAIL_POLICY"
        dp = data["metrics"]["demographic_parity"]
        assert dp["max_diff"] > dp["threshold"]

    def test_equal_opportunity_violation_triggers_fail(self, tmp_path):
        """TPR below minimum triggers FAIL_POLICY."""
        import yaml
        bad_suite = {
            "test_vectors": {
                "equal_opportunity": [
                    {"group": "group_a", "true_positive_rate": 0.70, "tolerance": 0.02},
                ]
            },
            "thresholds": {
                "demographic_parity_max_diff": 0.05,
                "equal_opportunity_min": 0.95,
            }
        }
        bad_yaml = tmp_path / "bad_eo.yaml"
        bad_yaml.write_text(yaml.dump(bad_suite))
        inventory = tmp_path / "inv.json"
        inventory.write_text(json.dumps({"total_models": 1, "models": [], "scan_ts": ""}))
        out = tmp_path / "eo.json"
        r = subprocess.run(
            ["python", str(AR09_FAIRNESS),
             "--models", str(inventory),
             "--metrics", "equal_opportunity",
             "--test-dataset", str(bad_yaml),
             "--out", str(out)],
            capture_output=True, text=True
        )
        assert r.returncode == 1
        data = json.loads(out.read_text())
        assert data["status"] == "FAIL_POLICY"
        assert data["metrics"]["equal_opportunity"]["failing_groups"] != []


# ---------------------------------------------------------------------------
# AR-10 Fee Distribution Audit
# ---------------------------------------------------------------------------

class TestAR10Integration:
    def test_real_fee_policy_passes(self, tmp_path):
        """Real fee_allocation_policy.yaml passes 7-Saeulen check."""
        real_policy = SSID_ROOT / "23_compliance" / "fee_allocation_policy.yaml"
        out = tmp_path / "fee.json"
        r = subprocess.run(
            ["python", str(AR10_FEE),
             "--policy", str(real_policy),
             "--out", str(out)],
            capture_output=True, text=True
        )
        assert r.returncode == 0, f"Real fee policy failed: {r.stdout}"
        data = json.loads(out.read_text())
        assert data["status"] == "PASS"
        assert abs(data["total_percent"] - 2.00) < 0.001
        assert data["pillar_count"] == 7

    def test_real_subscription_policy_passes(self, tmp_path):
        """Real subscription_revenue_policy.yaml passes 50/30/10/10 model."""
        real_policy = SSID_ROOT / "07_governance_legal" / "subscription_revenue_policy.yaml"
        out = tmp_path / "sub.json"
        r = subprocess.run(
            ["python", str(AR10_SUB),
             "--policy", str(real_policy),
             "--out", str(out)],
            capture_output=True, text=True
        )
        assert r.returncode == 0, r.stdout
        data = json.loads(out.read_text())
        assert data["status"] == "PASS"

    def test_policy_with_wrong_distribution_blocked(self, tmp_path):
        """Fee policy with wrong distribution model (not 50/30/10/10) is blocked."""
        import yaml
        bad_policy = {
            "distribution": {
                "protocol_development": {"percent": 40, "label": "X"},
                "community_rewards": {"percent": 40, "label": "Y"},
                "dao_governance": {"percent": 10, "label": "Z"},
                "operational_reserve": {"percent": 10, "label": "W"},
            },
            "sum_must_equal": 100
        }
        p = tmp_path / "bad_sub.yaml"
        p.write_text(yaml.dump(bad_policy))
        out = tmp_path / "result.json"
        r = subprocess.run(
            ["python", str(AR10_SUB),
             "--policy", str(p),
             "--out", str(out)],
            capture_output=True, text=True
        )
        assert r.returncode == 1, "Wrong distribution model must FAIL (DENY path)"
        data = json.loads(out.read_text())
        assert data["status"] == "FAIL_POLICY"
        assert data["mismatches"] != []

    def test_dao_params_out_of_range_blocked(self, tmp_path):
        """DAO param outside policy range triggers FAIL_QA."""
        real_policy = SSID_ROOT / "07_governance_legal" / "subscription_revenue_policy.yaml"
        # quorum of 5% is below min (10%)
        bad_params = tmp_path / "bad_params.json"
        bad_params.write_text(json.dumps({
            "min_quorum_percent": 5,       # below min=10
            "min_vote_duration_hours": 72,
            "max_proposal_fee_percent": 0.1,
            "treasury_withdrawal_cap_percent": 5,
        }))
        out = tmp_path / "dao.json"
        r = subprocess.run(
            ["python", str(AR10_DAO),
             "--policy", str(real_policy),
             "--actual-params", str(bad_params),
             "--out", str(out)],
            capture_output=True, text=True
        )
        assert r.returncode == 1, "Out-of-range DAO param must FAIL_QA (DENY path)"
        data = json.loads(out.read_text())
        assert data["status"] == "FAIL_QA"
        assert "min_quorum_percent" in data["failures"]
