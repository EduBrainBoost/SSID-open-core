#!/bin/bash
# SSID-open-core Phase 9 Execution (Option A)
# Thin Bash wrapper for Python orchestrator

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Default staging directory (temporary)
STAGING_DIR="${STAGING_DIR:-/tmp/ssid-phase9-staging-$(date +%s)}"

# Parse arguments
DRY_RUN=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN="--dry-run"
            shift
            ;;
        *)
            shift
            ;;
    esac
done

echo "========================================================================="
echo "SSID-open-core Phase 9 Execution (Option A)"
echo "========================================================================="
echo ""
echo "Source repository: $REPO_ROOT"
echo "Target repository: EduBrainBoost/SSID-open-core"
echo "Staging directory: $STAGING_DIR"
if [ -n "$DRY_RUN" ]; then
    echo "Mode: DRY-RUN"
fi
echo ""

# Call Python orchestrator
python3 "$SCRIPT_DIR/phase9_execute_option_a.py" \
    --source-repo "$REPO_ROOT" \
    --target-repo "EduBrainBoost/SSID-open-core" \
    --staging-dir "$STAGING_DIR" \
    $DRY_RUN

exit $?
