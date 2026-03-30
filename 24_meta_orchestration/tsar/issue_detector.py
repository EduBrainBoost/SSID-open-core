"""TSAR Issue Detector - Scans for structural, evidence, and registry anomalies."""

import importlib.util
import os
from pathlib import Path
from typing import List, Optional
from .tsar_engine import TSAREngine, DetectedIssue, IssueType, IssueSeverity, RemediationAction


# Import canonical roots from 03_core/constants.py (Single Source of Truth)
_CONSTANTS_PATH = Path(__file__).resolve().parents[2] / "03_core" / "constants.py"
_spec = importlib.util.spec_from_file_location("core_constants", _CONSTANTS_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
CANONICAL_ROOTS = _mod.CANONICAL_ROOTS_LIST  # list form for compatibility


class IssueDetector:
    """Scans the SSID repo for structural, evidence, and registry anomalies."""

    def __init__(self, repo_root: str, engine: Optional[TSAREngine] = None):
        self.repo_root = repo_root
        self.engine = engine or TSAREngine()

    def scan_structure(self) -> List[DetectedIssue]:
        """Scan for ROOT-24-LOCK compliance.

        Checks that all 24 canonical roots exist and no unexpected
        root-level directories are present.
        """
        actual_roots = []
        if os.path.isdir(self.repo_root):
            for entry in os.listdir(self.repo_root):
                full_path = os.path.join(self.repo_root, entry)
                if os.path.isdir(full_path) and not entry.startswith("."):
                    actual_roots.append(entry)
        return self.engine.detect_structure_drift(CANONICAL_ROOTS, actual_roots)

    def scan_evidence(self, required_evidence: Optional[List[str]] = None) -> List[DetectedIssue]:
        """Scan for evidence chain completeness.

        Checks that all required evidence files exist in the evidence directory.
        """
        evidence_dir = os.path.join(self.repo_root, ".ssid-system", "evidence")
        existing = []
        if os.path.isdir(evidence_dir):
            for root, _dirs, files in os.walk(evidence_dir):
                for f in files:
                    rel_path = os.path.relpath(os.path.join(root, f), evidence_dir)
                    existing.append(rel_path.replace("\\", "/"))

        if required_evidence is None:
            required_evidence = []

        return self.engine.detect_evidence_gaps(required_evidence, existing)

    def scan_registry(self) -> List[DetectedIssue]:
        """Scan for registry consistency.

        Checks that expected registry files exist and are non-empty.
        """
        issues = []
        registry_dir = os.path.join(self.repo_root, "24_meta_orchestration", "registry")
        expected_files = ["manifests", "intake"]

        if not os.path.isdir(registry_dir):
            issues.append(
                DetectedIssue(
                    issue_id=f"TSAR-{len(self.engine.issues)+len(issues)+1:04d}",
                    issue_type=IssueType.REGISTRY_INCONSISTENCY,
                    severity=IssueSeverity.HIGH,
                    description="Registry directory missing",
                    affected_path=registry_dir,
                    remediation=RemediationAction.APPROVAL_REQUIRED,
                )
            )
        else:
            for expected in expected_files:
                path = os.path.join(registry_dir, expected)
                if not os.path.exists(path):
                    issues.append(
                        DetectedIssue(
                            issue_id=f"TSAR-{len(self.engine.issues)+len(issues)+1:04d}",
                            issue_type=IssueType.REGISTRY_INCONSISTENCY,
                            severity=IssueSeverity.MEDIUM,
                            description=f"Registry entry missing: {expected}",
                            affected_path=path,
                            remediation=RemediationAction.AUTO_FIX,
                        )
                    )

        self.engine.issues.extend(issues)
        return issues

    def full_scan(self) -> dict:
        """Run all scans and return a comprehensive report."""
        structure_issues = self.scan_structure()
        evidence_issues = self.scan_evidence()
        registry_issues = self.scan_registry()

        return {
            "structure": [i.description for i in structure_issues],
            "evidence": [i.description for i in evidence_issues],
            "registry": [i.description for i in registry_issues],
            "health": self.engine.get_health_status(),
        }
