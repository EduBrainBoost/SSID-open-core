#!/bin/bash

#
# SBOM Automation Script
# Generates Software Bill-Of-Materials (SBOM) for SSID repositories
# Supports: SPDX JSON, CycloneDX XML
# Usage: ./sbom-automation.sh --repo <repo-name> --format spdx-json
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Defaults
REPO_NAME="${REPO_NAME:-SSID}"
FORMAT="${FORMAT:-spdx-json}"
OUTPUT_DIR="sbom-output"
DRY_RUN=false
SCAN_VULNS=false

# Supported repos
SUPPORTED_REPOS=("SSID" "SSID-EMS" "SSID-orchestrator" "SSID-docs" "SSID-open-core")

# Help
usage() {
  cat << EOF
Usage: $0 [OPTIONS]

Options:
  --repo <name>           Target repository name (default: SSID)
                         Supported: ${SUPPORTED_REPOS[@]}
  --format <format>       SBOM format: spdx-json, cyclonedx-xml (default: spdx-json)
  --output <dir>         Output directory (default: sbom-output)
  --scan-vulns           Run Grype vulnerability scan (default: false)
  --dry-run              Show what would be done without executing
  --help                 Show this help message

Examples:
  # Generate SPDX JSON SBOM for SSID
  ./sbom-automation.sh --repo SSID --format spdx-json

  # Generate with vulnerability scan
  ./sbom-automation.sh --repo SSID-EMS --scan-vulns

  # Dry run
  ./sbom-automation.sh --dry-run
EOF
  exit 0
}

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --repo)
      REPO_NAME="$2"
      shift 2
      ;;
    --format)
      FORMAT="$2"
      shift 2
      ;;
    --output)
      OUTPUT_DIR="$2"
      shift 2
      ;;
    --scan-vulns)
      SCAN_VULNS=true
      shift
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --help)
      usage
      ;;
    *)
      echo -e "${RED}Unknown option: $1${NC}"
      usage
      ;;
  esac
done

# Validate repo name
if [[ ! " ${SUPPORTED_REPOS[@]} " =~ " ${REPO_NAME} " ]]; then
  echo -e "${RED}Error: Unsupported repository '${REPO_NAME}'${NC}"
  echo "Supported repos: ${SUPPORTED_REPOS[@]}"
  exit 1
fi

# Validate format
case "$FORMAT" in
  spdx-json | cyclonedx-xml)
    ;;
  *)
    echo -e "${RED}Error: Unsupported format '${FORMAT}'${NC}"
    echo "Supported formats: spdx-json, cyclonedx-xml"
    exit 1
    ;;
esac

# Print banner
cat << EOF
${BLUE}
================================================================================
SBOM Generation Tool
================================================================================
Repo:           ${REPO_NAME}
Format:         ${FORMAT}
Output Dir:     ${OUTPUT_DIR}
Vulnerability:  ${SCAN_VULNS}
Dry Run:        ${DRY_RUN}
================================================================================
${NC}
EOF

# Step 0: Check if Syft is installed
if ! command -v syft &> /dev/null; then
  echo -e "${YELLOW}⚠ Syft not found. Installing...${NC}"
  if [[ "$DRY_RUN" == false ]]; then
    curl -sSfL https://raw.githubusercontent.com/anchore/syft/main/install.sh | sh -s -- -b /usr/local/bin
    echo -e "${GREEN}✓ Syft installed${NC}"
  else
    echo "[DRY RUN] Would install Syft"
  fi
fi

# Step 1: Create output directory
echo -e "${BLUE}Step 1: Preparing output directory${NC}"
if [[ "$DRY_RUN" == false ]]; then
  mkdir -p "$OUTPUT_DIR"
  echo -e "${GREEN}✓ Output directory ready: $OUTPUT_DIR${NC}"
else
  echo "[DRY RUN] Would create directory: $OUTPUT_DIR"
fi

# Step 2: Generate SBOM
echo -e "${BLUE}Step 2: Generating SBOM${NC}"

TIMESTAMP=$(date -u +%Y%m%d_%H%M%S)
case "$FORMAT" in
  spdx-json)
    SBOM_FILE="${OUTPUT_DIR}/SBOM_${REPO_NAME}_${TIMESTAMP}.json"
    SBOM_LATEST="${OUTPUT_DIR}/SBOM_LATEST.json"
    if [[ "$DRY_RUN" == false ]]; then
      echo "  Running: syft . -o spdx-json > ${SBOM_FILE}"
      syft . -o spdx-json > "$SBOM_FILE" 2>&1 || { echo -e "${RED}✗ SBOM generation failed${NC}"; exit 1; }
      cp "$SBOM_FILE" "$SBOM_LATEST"
      echo -e "${GREEN}✓ SBOM generated: $SBOM_FILE${NC}"
    else
      echo "[DRY RUN] Would generate SPDX JSON SBOM"
    fi
    ;;
  cyclonedx-xml)
    SBOM_FILE="${OUTPUT_DIR}/SBOM_${REPO_NAME}_${TIMESTAMP}.xml"
    SBOM_LATEST="${OUTPUT_DIR}/SBOM_LATEST.xml"
    if [[ "$DRY_RUN" == false ]]; then
      echo "  Running: syft . -o cyclonedx-xml > ${SBOM_FILE}"
      syft . -o cyclonedx-xml > "$SBOM_FILE" 2>&1 || { echo -e "${RED}✗ SBOM generation failed${NC}"; exit 1; }
      cp "$SBOM_FILE" "$SBOM_LATEST"
      echo -e "${GREEN}✓ SBOM generated: $SBOM_FILE${NC}"
    else
      echo "[DRY RUN] Would generate CycloneDX XML SBOM"
    fi
    ;;
esac

# Step 3: Vulnerability scan (optional)
if [[ "$SCAN_VULNS" == true ]]; then
  echo -e "${BLUE}Step 3: Running vulnerability scan${NC}"

  if ! command -v grype &> /dev/null; then
    echo -e "${YELLOW}⚠ Grype not found. Installing...${NC}"
    if [[ "$DRY_RUN" == false ]]; then
      curl -sSfL https://raw.githubusercontent.com/anchore/grype/main/install.sh | sh -s -- -b /usr/local/bin
      echo -e "${GREEN}✓ Grype installed${NC}"
    else
      echo "[DRY RUN] Would install Grype"
    fi
  fi

  VULN_REPORT="${OUTPUT_DIR}/${REPO_NAME}_vulnerabilities.txt"
  VULN_JSON="${OUTPUT_DIR}/${REPO_NAME}_vulnerabilities.json"

  if [[ "$DRY_RUN" == false && -f "$SBOM_FILE" ]]; then
    echo "  Running: grype $SBOM_FILE"
    grype "$SBOM_FILE" --output table > "$VULN_REPORT" 2>&1 || true
    grype "$SBOM_FILE" --output json > "$VULN_JSON" 2>&1 || true
    echo -e "${GREEN}✓ Vulnerability scan complete${NC}"
    echo ""
    cat "$VULN_REPORT"
  else
    echo "[DRY RUN] Would run Grype vulnerability scan"
  fi
fi

# Step 4: Summary
echo ""
echo -e "${BLUE}================================================================================
Summary
================================================================================${NC}"
echo "Repo:       $REPO_NAME"
echo "Format:     $FORMAT"
if [[ "$DRY_RUN" == false && -f "$SBOM_FILE" ]]; then
  SBOM_SIZE=$(du -h "$SBOM_FILE" | cut -f1)
  COMPONENT_COUNT=$(grep -c '"name"' "$SBOM_FILE" 2>/dev/null || echo "unknown")
  echo "SBOM File:  $SBOM_FILE ($SBOM_SIZE)"
  echo "Components: $COMPONENT_COUNT"
  echo -e "${GREEN}✓ SBOM Generation: SUCCESS${NC}"
else
  echo -e "${YELLOW}⚠ Dry run mode${NC}"
fi

if [[ "$SCAN_VULNS" == true && "$DRY_RUN" == false && -f "$VULN_JSON" ]]; then
  VULN_COUNT=$(grep -o '"vulnerability"' "$VULN_JSON" 2>/dev/null | wc -l)
  echo "Vulnerabilities: $VULN_COUNT"
fi

echo -e "${BLUE}================================================================================${NC}"
