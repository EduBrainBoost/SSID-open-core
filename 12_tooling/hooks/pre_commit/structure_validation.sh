#!/bin/bash
# Pre-commit hook for structure validation
# Version: 1.0
# Date: 2025-09-15

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"

echo "Running SSID OpenCore structure validation..."

# Run structure guard
if ! "$ROOT_DIR/12_tooling/scripts/structure_guard.sh" validate; then
    echo "COMMIT BLOCKED: Structure validation failed"
    echo "Please fix structure issues before committing"
    exit 1
fi

echo "Structure validation passed"
exit 0