#!/usr/bin/env bash
# CI Guard: pytest cage blocker — verifies pytest.ini and cache_dir config
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$REPO_ROOT"

echo "[GUARD] pytest cage blocker"

# Check pytest.ini exists
if [ ! -f "pytest.ini" ]; then
  echo "[FAIL] pytest.ini not found"
  exit 1
fi

# Check cache_dir is set to cage path
if ! grep -q "cache_dir=24_meta_orchestration/triggers/ci/pytest_cage/.pytest_cache" pytest.ini; then
  echo "[FAIL] pytest.ini missing cage cache_dir"
  exit 1
fi

# Check testpaths includes unit
if ! grep -q "11_test_simulation/tests/unit" pytest.ini; then
  echo "[FAIL] pytest.ini testpaths missing 11_test_simulation/tests/unit"
  exit 1
fi

echo "[PASS] pytest cage blocker"
