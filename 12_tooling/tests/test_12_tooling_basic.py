#!/usr/bin/env python3
"""Basic infrastructure tests for SSID root: 12_tooling.

Verifies:
- src/__init__.py exists
- all .py files in src/ have valid Python syntax
- policies/policy.yaml exists and is valid YAML
"""
from __future__ import annotations

import ast
import py_compile
import tempfile
from pathlib import Path

import pytest
import yaml

ROOT_DIR = Path(__file__).resolve().parents[1]
ROOT_NAME = ROOT_DIR.name
SRC_DIR = ROOT_DIR / "src"
POLICY_FILE = ROOT_DIR / "policies" / "policy.yaml"


def test_src_init_exists() -> None:
    """src/__init__.py must exist."""
    assert (SRC_DIR / "__init__.py").exists(), (
        f"{ROOT_NAME}/src/__init__.py is missing"
    )


def test_src_py_files_valid_syntax() -> None:
    """All .py files in src/ must have valid Python syntax."""
    py_files = list(SRC_DIR.glob("*.py"))
    if not py_files:
        pytest.skip(f"{ROOT_NAME}/src/ contains no .py files (only __init__.py check is sufficient)")

    errors: list[str] = []
    for py_file in py_files:
        try:
            py_compile.compile(str(py_file), doraise=True)
        except py_compile.PyCompileError as exc:
            errors.append(f"{py_file.name}: {exc}")

    assert not errors, "Syntax errors found:\n" + "\n".join(errors)


def test_policy_yaml_exists() -> None:
    """policies/policy.yaml must exist."""
    assert POLICY_FILE.exists(), (
        f"{ROOT_NAME}/policies/policy.yaml is missing"
    )


def test_policy_yaml_valid() -> None:
    """policies/policy.yaml must be valid YAML."""
    assert POLICY_FILE.exists(), (
        f"{ROOT_NAME}/policies/policy.yaml is missing — cannot validate"
    )
    with open(POLICY_FILE, encoding="utf-8") as fh:
        content = fh.read()
    try:
        parsed = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        pytest.fail(f"{ROOT_NAME}/policies/policy.yaml is not valid YAML: {exc}")
    assert parsed is not None, (
        f"{ROOT_NAME}/policies/policy.yaml is empty or null"
    )
