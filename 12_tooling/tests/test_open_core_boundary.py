# Test Open Core Boundary Policy
# pytest: test_open_core_boundary.py
import os
import pathlib

ROOT = pathlib.Path(__file__).parent.parent.resolve()

FORBIDDEN_PATHS = [
    '*/shards/*',
    '24_meta_orchestration/registry',
    '24_meta_orchestration/report_bus',
    '24_meta_orchestration/tsar',
    '24_meta_orchestration/incident',
    '24_meta_orchestration/triggers',
    '24_meta_orchestration/version_management',
    '*/__pycache__/*',
    '*.pyc',
    'backup_*.tar.gz',
    'ssid_open_core_export.zip',
    'ssid_open_core_export/',
    'DEPLOYMENT_EVIDENCE.md',
    'GOVERNANCE_AUDIT_FINAL_REPORT.md',
    'LOCAL_ONLY_VERIFICATION_POLICY.md',
    'BOUNDARY_VIOLATIONS_PHASE1.txt',
]

ALLOWED_ROOTS = [
    '03_core/validators/sot/',
    '12_tooling/cli/',
    '12_tooling/scripts/',
    '12_tooling/tests/export/',
    '16_codex/decisions/',
    '16_codex/contracts/sot/',
    '23_compliance/policies/sot/',
    '23_compliance/exceptions/',
    '24_meta_orchestration/dispatcher/',
]

def test_no_forbidden_paths():
    """Verify no forbidden paths exist in the repo"""
    found = []
    for forbidden in FORBIDDEN_PATHS:
        matches = list(ROOT.glob(forbidden))
        if matches:
            found.extend(matches)
    assert not found, f"Found forbidden paths: {found}"

def test_boundary_policy():
    """Verify boundary policy is enforced"""
    assert (ROOT / '16_codex' / 'decisions' / 'ADR_001_OPEN_CORE_BOUNDARY_CANON.md').exists()
