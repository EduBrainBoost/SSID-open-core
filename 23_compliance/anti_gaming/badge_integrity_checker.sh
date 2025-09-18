#!/bin/bash
# Badge Integrity Checker
# Verifies badge calculation formulas and sources
# Version: 1.0
# Date: 2025-09-15

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Function to verify badge formulas
function_verify_formulas() {
    echo "Verifying badge calculation formulas..."

    local errors=0

    # Check structure guard badge formula
    local structure_guard="$ROOT_DIR/12_tooling/scripts/structure_guard.sh"
    if [ -f "$structure_guard" ]; then
        # Verify line 127 contains score calculation
        if ! grep -n "passed_checks / total_checks \* 100" "$structure_guard" | grep -q "127\|calculate_structure_score"; then
            echo "WARNING: Badge formula may have moved from expected location"
        fi

        # Verify formula logic exists
        if ! grep -q "scale=2.*passed_checks.*total_checks.*100" "$structure_guard"; then
            echo "ERROR: Structure compliance formula not found or modified"
            errors=$((errors + 1))
        fi
    else
        echo "ERROR: Structure guard script not found"
        errors=$((errors + 1))
    fi

    # Check metrics configuration
    local metrics_file="$ROOT_DIR/23_compliance/metrics/public_metrics_v1.0.yaml"
    if [ -f "$metrics_file" ]; then
        if ! grep -q "structure_compliance" "$metrics_file"; then
            echo "WARNING: Metrics configuration may be missing or modified"
        fi
    fi

    return $errors
}

# Source verification
verify_source_references() {
    echo "Verifying source references..."

    local sources_file="$ROOT_DIR/23_compliance/governance/source_of_truth.md"
    if [ -f "$sources_file" ]; then
        # Check if source references are documented
        if ! grep -q "structure_guard.sh:line_127" "$sources_file"; then
            echo "WARNING: Source references may need updating"
        fi
    fi
}

# Main verification
main() {
    echo "SSID OpenCore - Badge Integrity Checker"
    echo "========================================"

    local total_errors=0

    function_verify_formulas
    total_errors=$((total_errors + $?))

    verify_source_references

    echo ""
    if [ $total_errors -eq 0 ]; then
        echo "✅ Badge integrity check PASSED"
        exit 0
    else
        echo "❌ Badge integrity check FAILED with $total_errors errors"
        exit 1
    fi
}

# Command line handling
case "${1:-verify}" in
    "verify-formulas")
        function_verify_formulas
        ;;
    "source-check")
        verify_source_references
        ;;
    *)
        main
        ;;
esac