# DEPRECATED: REDUNDANT — Canonical tool is 03_core/validators/base_guard.py
#!/usr/bin/env bash
# SSID Structure Validation — wrapper for structure_guard + policy checks
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

echo "=== SSID Structure Validation ==="
echo "Running structure_guard..."
bash "$REPO_ROOT/12_tooling/scripts/structure_guard.sh" || exit 24

echo "Running policy check..."
python "$REPO_ROOT/24_meta_orchestration/triggers/ci/gates/structure_lock_l3.py" || exit 24

echo "=== STRUCTURE VALIDATION PASS ==="
