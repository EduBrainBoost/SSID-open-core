#!/bin/bash
# structure_guard.sh - SSID OpenCore Structure Validation
# Version: 1.0
# Date: 2025-09-15

set -e

VERSION="1.0"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Badge calculation logic (line 89-95)
calculate_structure_score() {
    local passed_checks=0
    local total_checks=0

    # Check for 24 root modules
    for module in {01..24}; do
        total_checks=$((total_checks + 1))
        case $module in
            01) module_name="01_ai_layer" ;;
            02) module_name="02_audit_logging" ;;
            03) module_name="03_core" ;;
            04) module_name="04_deployment" ;;
            05) module_name="05_documentation" ;;
            06) module_name="06_data_pipeline" ;;
            07) module_name="07_governance_legal" ;;
            08) module_name="08_identity_score" ;;
            09) module_name="09_meta_identity" ;;
            10) module_name="10_interoperability" ;;
            11) module_name="11_test_simulation" ;;
            12) module_name="12_tooling" ;;
            13) module_name="13_ui_layer" ;;
            14) module_name="14_zero_time_auth" ;;
            15) module_name="15_infra" ;;
            16) module_name="16_codex" ;;
            17) module_name="17_observability" ;;
            18) module_name="18_data_layer" ;;
            19) module_name="19_adapters" ;;
            20) module_name="20_foundation" ;;
            21) module_name="21_post_quantum_crypto" ;;
            22) module_name="22_datasets" ;;
            23) module_name="23_compliance" ;;
            24) module_name="24_meta_orchestration" ;;
        esac

        if [ -d "$ROOT_DIR/$module_name" ]; then
            passed_checks=$((passed_checks + 1))
        fi
    done

    # Line 127: Badge score calculation
    echo $(( passed_checks * 100 / total_checks ))
}

# Structure validation
validate_structure() {
    echo "SSID OpenCore Structure Guard v$VERSION"
    echo "Validating structure against blueprint..."

    local errors=0

    # Validate 24 root modules exist
    for module in 01_ai_layer 02_audit_logging 03_core 04_deployment 05_documentation 06_data_pipeline 07_governance_legal 08_identity_score 09_meta_identity 10_interoperability 11_test_simulation 12_tooling 13_ui_layer 14_zero_time_auth 15_infra 16_codex 17_observability 18_data_layer 19_adapters 20_foundation 21_post_quantum_crypto 22_datasets 23_compliance 24_meta_orchestration; do
        if [ ! -d "$ROOT_DIR/$module" ]; then
            echo "ERROR: Missing module directory: $module"
            errors=$((errors + 1))
        else
            # Check for required MUST files
            if [ ! -f "$ROOT_DIR/$module/module.yaml" ]; then
                echo "WARNING: Missing module.yaml in $module"
            fi
            if [ ! -f "$ROOT_DIR/$module/README.md" ]; then
                echo "WARNING: Missing README.md in $module"
            fi
            if [ ! -d "$ROOT_DIR/$module/docs" ]; then
                echo "WARNING: Missing docs/ directory in $module"
            fi
            if [ ! -d "$ROOT_DIR/$module/src" ]; then
                echo "WARNING: Missing src/ directory in $module"
            fi
            if [ ! -d "$ROOT_DIR/$module/tests" ]; then
                echo "WARNING: Missing tests/ directory in $module"
            fi
        fi
    done

    # Calculate and display score
    local score=$(calculate_structure_score)
    echo "Structure Compliance Score: $score%"

    if [ $errors -eq 0 ]; then
        echo "Structure validation PASSED"
        return 0
    else
        echo "Structure validation FAILED with $errors errors"
        return 1
    fi
}

# Main execution
case "${1:-validate}" in
    "validate")
        validate_structure
        ;;
    "score")
        calculate_structure_score
        ;;
    "evidence")
        validate_structure 2>&1 | tee "$ROOT_DIR/23_compliance/evidence/ci_runs/structure_validation_results/$(date +%Y%m%d_%H%M%S).log"
        ;;
    "version-check")
        echo "Structure Guard Version: $VERSION"
        ;;
    *)
        echo "Usage: $0 {validate|score|evidence|version-check}"
        exit 1
        ;;
esac