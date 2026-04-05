"""Shared pytest fixtures for content pipeline tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Ensure the pipelines package is importable without installation
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[4]  # SSID-open-core root
_PIPELINE_PARENT = _REPO_ROOT / "03_core" / "pipelines"

if str(_PIPELINE_PARENT) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_PARENT))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_dir(tmp_path: Path) -> Path:
    """Provide a clean temporary directory."""
    return tmp_path


@pytest.fixture()
def sample_markdown_file(tmp_path: Path) -> Path:
    """Write a sample markdown file and return its path."""
    md = tmp_path / "sample_doc.md"
    md.write_text(
        "# Sample Document\n\nThis is a **governance** policy document.\n\n"
        "It covers compliance requirements and audit trails.\n",
        encoding="utf-8",
    )
    return md


@pytest.fixture()
def sample_yaml_file(tmp_path: Path) -> Path:
    """Write a sample YAML file and return its path."""
    y = tmp_path / "sample_config.yaml"
    y.write_text(
        "title: Architecture Decision Record\n"
        "id: ADR-001\n"
        "status: accepted\n"
        "category: architecture\n"
        "description: Decision about modular engine design\n",
        encoding="utf-8",
    )
    return y


@pytest.fixture()
def sample_json_file(tmp_path: Path) -> Path:
    """Write a sample JSON file and return its path."""
    j = tmp_path / "sample_contract.json"
    import json

    j.write_text(
        json.dumps(
            {
                "title": "Service Level Agreement",
                "id": "CONTRACT-001",
                "category": "contract",
                "parties": ["SSID", "Partner"],
                "terms": "Standard SLA terms and conditions apply.",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return j


@pytest.fixture()
def sample_policy_file(tmp_path: Path) -> Path:
    """Write a sample Rego policy file and return its path."""
    p = tmp_path / "allow_access.rego"
    p.write_text(
        'package ssid.governance\n\ndefault allow = false\n\nallow {\n    input.role == "admin"\n}\n',
        encoding="utf-8",
    )
    return p


@pytest.fixture()
def sample_source_dir(
    tmp_path: Path,
    sample_markdown_file: Path,
    sample_yaml_file: Path,
    sample_json_file: Path,
    sample_policy_file: Path,
) -> Path:
    """Return a directory containing all sample files."""
    return tmp_path
