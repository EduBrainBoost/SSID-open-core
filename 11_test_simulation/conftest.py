"""Repo-local pytest fixtures for 11_test_simulation tests."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_TMP_ROOT = REPO_ROOT / ".ssid-system" / "test_tmp"


@pytest.fixture
def tmp_path() -> Path:
    """Workspace-local tmp path outside the git repo to avoid locked Windows temp roots."""
    WORKSPACE_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    path = WORKSPACE_TMP_ROOT / f"pytest-{uuid4().hex[:8]}"
    path.mkdir(parents=True, exist_ok=True)
    return path
