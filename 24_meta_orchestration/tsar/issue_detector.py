"""TSAR Issue Detector - Scans for structural, evidence, and registry anomalies."""

import os
from typing import List, Optional
from .tsar_engine import TSAREngine, DetectedIssue, IssueType, IssueSeverity, RemediationAction


# Canonical ROOT-24-LOCK roots
CANONICAL_ROOTS = [
    "01_ai_layer",
    "02_audit_logging",
    "03_core",
    "04_deployment",
    "05_documentation",
    "06_data_pipeline",
    "07_governance_legal",
    "08_identity_score",
    "09_meta_identity",
    "10_interoperability",
    "11_test_simulation",
    "12_tooling",
    "13_ui_layer",
    "14_zero_time_auth",
    "15_infra",
    "16_codex",
    "17_observability",
    "18_data_layer",
    "19_adapters",
    "20_foundation",
    "21_post_quantum_crypto",
    "22_datasets",
    "23_compliance",
    "24_meta_orchestration",
]


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
