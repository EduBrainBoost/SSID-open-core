# Badge & Metrics Source References

## Structure Compliance Badge
- **Source:** `12_tooling/scripts/structure_guard.sh:line_127`
- **Formula:** Line 89-95 in structure_guard.sh
- **Threshold:** Defined in `23_compliance/metrics/public_metrics_v1.0.yaml:line_8`
- **Dependencies:** `23_compliance/policies/structure_policy.yaml`

## Test Coverage Badge
- **Source:** `pytest.ini:coverage_threshold` + `.github/workflows/test.yml:line_45`
- **Formula:** pytest-cov standard calculation
- **Threshold:** 90% as defined in `23_compliance/metrics/threshold_rationale.yaml:line_15`
- **Dependencies:** All module `tests/` directories

## Build Status Badge
- **Source:** `.github/workflows/ci.yml`
- **Integration:** `24_meta_orchestration/triggers/ci/gates/structure_lock_l3.py`
- **Dependencies:** All critical files listed above

## Anti-Gaming Controls
- **Circular Dependencies:** `23_compliance/anti_gaming/circular_dependency_validator.py:class_CircularValidator`
- **Badge Integrity:** `23_compliance/anti_gaming/badge_integrity_checker.sh:function_verify_formulas`
- **Dependency Graph:** `23_compliance/anti_gaming/dependency_graph_generator.py:export_graph`