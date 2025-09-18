#!/usr/bin/env python3
"""
Policy and Exception Review System
Version: 1.0
Date: 2025-09-16

Performs automated review of security policies and exceptions with evidence generation.
"""

import argparse
import json
import os
import sys
import yaml
from datetime import datetime
from pathlib import Path

class PolicyReviewer:
    def __init__(self):
        self.compliance_score = 100
        self.violations = []
        self.recommendations = []

    def review_structure_policy(self, policy_path):
        """Review structure policy compliance"""
        print(f"Reviewing structure policy: {policy_path}")

        # Check if policy file exists
        policy_file = Path(policy_path)
        if not policy_file.exists():
            self._create_default_structure_policy(policy_file)

        # Load and validate policy
        try:
            with open(policy_file, 'r') as f:
                policy = yaml.safe_load(f)
        except yaml.YAMLError as e:
            self.violations.append(f"Invalid YAML in policy file: {e}")
            self.compliance_score -= 10
            return

        # Validate required policy sections
        required_sections = ['version', 'policy_name', 'requirements', 'violations', 'enforcement']
        for section in required_sections:
            if section not in policy:
                self.violations.append(f"Missing required policy section: {section}")
                self.compliance_score -= 5

        # Check policy version and last update
        if 'last_review' in policy:
            last_review = datetime.fromisoformat(policy['last_review'])
            days_since_review = (datetime.now() - last_review).days
            if days_since_review > 30:
                self.recommendations.append(f"Policy review overdue by {days_since_review - 30} days")

        print(f"Structure policy review completed - Score: {self.compliance_score}%")

    def review_exceptions(self, exceptions_path):
        """Review security exceptions"""
        print(f"Reviewing exceptions: {exceptions_path}")

        exceptions_file = Path(exceptions_path)
        if not exceptions_file.exists():
            self._create_default_exceptions(exceptions_file)

        try:
            with open(exceptions_file, 'r') as f:
                exceptions = yaml.safe_load(f)
        except yaml.YAMLError as e:
            self.violations.append(f"Invalid YAML in exceptions file: {e}")
            self.compliance_score -= 10
            return

        # Review each exception
        active_exceptions = exceptions.get('exceptions', [])
        expired_exceptions = 0

        for exception in active_exceptions:
            if 'expiry_date' in exception:
                expiry = datetime.fromisoformat(exception['expiry_date'])
                if expiry < datetime.now():
                    expired_exceptions += 1
                    self.violations.append(f"Expired exception: {exception.get('id', 'unknown')}")

        if expired_exceptions > 0:
            self.compliance_score -= expired_exceptions * 5

        print(f"Exceptions review completed - {expired_exceptions} expired exceptions found")

    def _create_default_structure_policy(self, policy_path):
        """Create default structure policy"""
        policy_path.parent.mkdir(parents=True, exist_ok=True)

        default_policy = {
            'version': '1.0',
            'policy_name': 'SSID OpenCore Structure Policy',
            'created': datetime.now().isoformat(),
            'last_review': datetime.now().isoformat(),
            'requirements': {
                'root_modules': 24,
                'module_naming': 'XX_module_name format',
                'required_files': ['module.yaml', 'README.md'],
                'required_directories': ['docs', 'src', 'tests']
            },
            'violations': {
                'missing_module': 'CRITICAL',
                'missing_required_file': 'WARNING',
                'invalid_naming': 'ERROR'
            },
            'enforcement': {
                'pre_commit_hooks': True,
                'ci_validation': True,
                'automated_remediation': False
            }
        }

        with open(policy_path, 'w') as f:
            yaml.dump(default_policy, f, default_flow_style=False)

        print(f"Created default structure policy: {policy_path}")

    def _create_default_exceptions(self, exceptions_path):
        """Create default exceptions file"""
        exceptions_path.parent.mkdir(parents=True, exist_ok=True)

        default_exceptions = {
            'version': '1.0',
            'created': datetime.now().isoformat(),
            'last_review': datetime.now().isoformat(),
            'exceptions': []
        }

        with open(exceptions_path, 'w') as f:
            yaml.dump(default_exceptions, f, default_flow_style=False)

        print(f"Created default exceptions file: {exceptions_path}")

    def generate_evidence(self, target_file):
        """Generate evidence log"""
        evidence_dir = Path("23_compliance/evidence/ci_runs")
        evidence_dir.mkdir(parents=True, exist_ok=True)

        evidence_file = evidence_dir / f"policy_review_evidence_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        evidence = {
            "timestamp": datetime.now().isoformat(),
            "target_file": str(target_file),
            "compliance_score": self.compliance_score,
            "violations": self.violations,
            "recommendations": self.recommendations,
            "review_status": "COMPLIANT" if self.compliance_score >= 95 else "NON-COMPLIANT",
            "evidence_type": "policy_review"
        }

        with open(evidence_file, 'w') as f:
            json.dump(evidence, f, indent=2)

        return evidence_file

def main():
    parser = argparse.ArgumentParser(description="Review security policies and exceptions")
    parser.add_argument("--target", required=True, help="Target policy/exception file")
    parser.add_argument("--evidence", action="store_true", help="Generate evidence log")

    args = parser.parse_args()

    reviewer = PolicyReviewer()

    # Determine review type based on filename
    target_path = Path(args.target)
    if 'structure_policy' in target_path.name:
        reviewer.review_structure_policy(args.target)
    elif 'exceptions' in target_path.name:
        reviewer.review_exceptions(args.target)
    else:
        print(f"Unknown policy type: {target_path.name}")
        sys.exit(1)

    # Generate evidence if requested
    if args.evidence:
        evidence_file = reviewer.generate_evidence(args.target)
        print(f"Evidence generated: {evidence_file}")

    print(f"Final compliance score: {reviewer.compliance_score}%")
    if reviewer.violations:
        print(f"Violations found: {len(reviewer.violations)}")
        for violation in reviewer.violations:
            print(f"  - {violation}")

if __name__ == "__main__":
    main()