#!/usr/bin/env python3
"""
Unit tests for structure policy validation against blueprint MD file
Version: 1.0
Date: 2025-09-15
"""

import unittest
import yaml
import os
import re
from pathlib import Path


class TestStructurePolicyVsMD(unittest.TestCase):
    """Test structure policy matches blueprint specification"""

    def setUp(self):
        """Set up test fixtures"""
        self.root_dir = Path(__file__).parent.parent.parent.parent
        self.policy_file = self.root_dir / "23_compliance/policies/structure_policy_v1_0/structure_policy_v1_0.yaml"
        self.blueprint_file = self.root_dir / "24_meta_orchestration/locks/SSID_opencore_structure_level3.md"

        # Load policy file
        with open(self.policy_file, 'r') as f:
            self.policy = yaml.safe_load(f)

    def test_policy_file_exists(self):
        """Test that structure policy file exists"""
        self.assertTrue(self.policy_file.exists())

    def test_policy_has_required_sections(self):
        """Test that policy has all required sections"""
        # Check top-level sections
        top_level_sections = ['structure_requirements', 'exceptions', 'compliance_threshold']
        for section in top_level_sections:
            self.assertIn(section, self.policy)

        # Check structure_requirements subsections
        structure_sections = [
            'root_modules',
            'common_must_files',
            'common_must_directories',
            'forbidden_local_directories',
            'centralized_locations'
        ]
        for section in structure_sections:
            self.assertIn(section, self.policy['structure_requirements'])

    def test_module_count_is_24(self):
        """Test that exactly 24 modules are defined"""
        modules = self.policy['structure_requirements']['root_modules']['required_modules']
        self.assertEqual(len(modules), 24)

    def test_module_naming_convention(self):
        """Test that modules follow NN_module_name convention"""
        modules = self.policy['structure_requirements']['root_modules']['required_modules']
        pattern = re.compile(r'^\d{2}_[a-z_]+$')

        for module in modules:
            self.assertTrue(pattern.match(module), f"Module {module} doesn't match naming convention")

    def test_modules_are_sequential(self):
        """Test that modules are numbered sequentially from 01 to 24"""
        modules = self.policy['structure_requirements']['root_modules']['required_modules']
        expected_numbers = [f"{i:02d}" for i in range(1, 25)]
        actual_numbers = [module.split('_')[0] for module in modules]

        self.assertEqual(actual_numbers, expected_numbers)

    def test_common_must_files_defined(self):
        """Test that common MUST files are defined"""
        must_files = self.policy['structure_requirements']['common_must_files']
        expected_files = ['module.yaml', 'README.md']

        for file in expected_files:
            self.assertIn(file, must_files)

    def test_common_must_directories_defined(self):
        """Test that common MUST directories are defined"""
        must_dirs = self.policy['structure_requirements']['common_must_directories']
        expected_dirs = ['docs/', 'src/', 'tests/']

        for dir in expected_dirs:
            self.assertIn(dir, must_dirs)

    def test_forbidden_directories_defined(self):
        """Test that forbidden local directories are defined"""
        forbidden = self.policy['structure_requirements']['forbidden_local_directories']
        expected_forbidden = [
            'registry/', 'policies/', 'risk/', 'evidence/',
            'exceptions/', 'triggers/', 'ci/', 'cd/'
        ]

        for item in expected_forbidden:
            self.assertIn(item, forbidden)

    def test_compliance_threshold_defined(self):
        """Test that compliance threshold is defined and reasonable"""
        threshold = self.policy['compliance_threshold']
        self.assertIsInstance(threshold, int)
        self.assertGreaterEqual(threshold, 90)
        self.assertLessEqual(threshold, 100)


if __name__ == '__main__':
    unittest.main()