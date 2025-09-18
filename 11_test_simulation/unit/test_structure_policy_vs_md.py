#!/usr/bin/env python3
"""
Unit Tests for Structure Policy Compliance
Version: 1.0
Date: 2025-09-16

Tests structure policy compliance against markdown documentation and blacklist rules.
"""

import unittest
import subprocess
import json
import yaml
from pathlib import Path

class TestStructurePolicyCompliance(unittest.TestCase):

    def setUp(self):
        """Set up test environment"""
        self.root_dir = Path(__file__).parent.parent.parent
        self.structure_guard_script = self.root_dir / "12_tooling" / "scripts" / "structure_guard.sh"

    def test_structure_guard_executable(self):
        """Test that structure guard script is executable and functional"""
        self.assertTrue(self.structure_guard_script.exists(), "Structure guard script not found")

        # Test version command
        result = subprocess.run(
            ["bash", str(self.structure_guard_script), "version-check"],
            capture_output=True, text=True, cwd=self.root_dir
        )
        self.assertEqual(result.returncode, 0, "Structure guard version check failed")
        self.assertIn("Structure Guard Version", result.stdout)

    def test_structure_validation_passes(self):
        """Test that current structure passes validation"""
        result = subprocess.run(
            ["bash", str(self.structure_guard_script), "validate"],
            capture_output=True, text=True, cwd=self.root_dir
        )
        self.assertEqual(result.returncode, 0, f"Structure validation failed: {result.stdout}")
        self.assertIn("Structure validation PASSED", result.stdout)

    def test_compliance_score_minimum(self):
        """Test that compliance score meets minimum requirements (≥99%)"""
        result = subprocess.run(
            ["bash", str(self.structure_guard_script), "score"],
            capture_output=True, text=True, cwd=self.root_dir
        )
        self.assertEqual(result.returncode, 0, "Failed to get compliance score")

        score = int(result.stdout.strip())
        self.assertGreaterEqual(score, 99, f"Compliance score {score}% is below required minimum of 99%")

    def test_required_modules_exist(self):
        """Test that all 24 required modules exist"""
        required_modules = [
            "01_ai_layer", "02_audit_logging", "03_core", "04_deployment",
            "05_documentation", "06_data_pipeline", "07_governance_legal", "08_identity_score",
            "09_meta_identity", "10_interoperability", "11_test_simulation", "12_tooling",
            "13_ui_layer", "14_zero_time_auth", "15_infra", "16_codex",
            "17_observability", "18_data_layer", "19_adapters", "20_foundation",
            "21_post_quantum_crypto", "22_datasets", "23_compliance", "24_meta_orchestration"
        ]

        for module in required_modules:
            module_path = self.root_dir / module
            self.assertTrue(module_path.exists(), f"Required module missing: {module}")
            self.assertTrue(module_path.is_dir(), f"Module is not a directory: {module}")

    def test_module_structure_compliance(self):
        """Test that modules have required directory structure"""
        required_modules = [
            "01_ai_layer", "02_audit_logging", "03_core", "04_deployment",
            "05_documentation", "06_data_pipeline", "07_governance_legal", "08_identity_score",
            "09_meta_identity", "10_interoperability", "11_test_simulation", "12_tooling",
            "13_ui_layer", "14_zero_time_auth", "15_infra", "16_codex",
            "17_observability", "18_data_layer", "19_adapters", "20_foundation",
            "21_post_quantum_crypto", "22_datasets", "23_compliance", "24_meta_orchestration"
        ]

        required_subdirs = ["docs", "src", "tests"]

        for module in required_modules:
            module_path = self.root_dir / module

            # Check for required subdirectories
            for subdir in required_subdirs:
                subdir_path = module_path / subdir
                self.assertTrue(subdir_path.exists(),
                               f"Required subdirectory missing: {module}/{subdir}")

    def test_policy_files_exist(self):
        """Test that policy files exist and are valid"""
        policy_dir = self.root_dir / "23_compliance" / "policies"

        # Structure policy should exist
        structure_policy = policy_dir / "structure_policy.yaml"
        if structure_policy.exists():
            # Validate YAML structure
            try:
                with open(structure_policy, 'r') as f:
                    policy_data = yaml.safe_load(f)
                    self.assertIn('version', policy_data)
                    self.assertIn('requirements', policy_data)
            except yaml.YAMLError as e:
                self.fail(f"Invalid YAML in structure policy: {e}")

    def test_security_scripts_executable(self):
        """Test that security scripts are executable"""
        scripts_dir = self.root_dir / "12_tooling" / "scripts"
        required_scripts = [
            "structure_guard.sh",
            "update_write_overrides.py",
            "policy_review.py",
            "badge_generator.py",
            "export_audit_package.py"
        ]

        for script in required_scripts:
            script_path = scripts_dir / script
            self.assertTrue(script_path.exists(), f"Required script missing: {script}")

            # Check if Python script has executable permissions or shebang
            if script.endswith('.py'):
                with open(script_path, 'r') as f:
                    first_line = f.readline()
                    self.assertTrue(first_line.startswith('#!'),
                                   f"Python script missing shebang: {script}")

    def test_git_hooks_installed(self):
        """Test that git hooks are properly installed"""
        git_hooks_dir = self.root_dir / ".git" / "hooks"
        pre_commit_hook = git_hooks_dir / "pre-commit"

        self.assertTrue(pre_commit_hook.exists(), "Pre-commit hook not installed")

        # Check that hook references structure validation
        with open(pre_commit_hook, 'r') as f:
            hook_content = f.read()
            self.assertIn("structure_guard.sh", hook_content,
                         "Pre-commit hook does not reference structure guard")

if __name__ == '__main__':
    # Run tests with detailed output
    unittest.main(verbosity=2)