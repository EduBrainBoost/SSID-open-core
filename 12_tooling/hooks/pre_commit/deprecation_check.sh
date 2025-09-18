#!/bin/bash
# Deprecation Check Pre-Commit Hook
# Version: 1.0
# Date: 2025-09-18
# Purpose: Check for deprecated items and version consistency

set -e

echo "🔍 Running deprecation check..."

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Counters
DEPRECATED_COUNT=0
VERSION_ISSUES=0
WARNINGS=0

# Function to check for deprecated items in YAML files
check_deprecated_yaml() {
    local file="$1"

    if grep -q "deprecated: true" "$file"; then
        echo -e "${YELLOW}⚠️  Found deprecated item in: $file${NC}"
        DEPRECATED_COUNT=$((DEPRECATED_COUNT + 1))

        # Check if replacement is specified
        if ! grep -q "replacement_available\|replaced_by\|successor" "$file"; then
            echo -e "${RED}❌ Deprecated item missing replacement specification in: $file${NC}"
            VERSION_ISSUES=$((VERSION_ISSUES + 1))
        fi

        # Check if deprecation_date is specified
        if ! grep -q "deprecation_date\|migration_deadline" "$file"; then
            echo -e "${YELLOW}⚠️  Deprecated item missing deprecation timeline in: $file${NC}"
            WARNINGS=$((WARNINGS + 1))
        fi
    fi
}

# Function to check version consistency
check_version_consistency() {
    local file="$1"

    # Check if version field exists
    if ! grep -q "version:" "$file"; then
        echo -e "${YELLOW}⚠️  Missing version field in: $file${NC}"
        WARNINGS=$((WARNINGS + 1))
        return
    fi

    # Check if date field exists
    if ! grep -q "date:" "$file"; then
        echo -e "${YELLOW}⚠️  Missing date field in: $file${NC}"
        WARNINGS=$((WARNINGS + 1))
    fi

    # Check if deprecated field exists
    if ! grep -q "deprecated:" "$file"; then
        echo -e "${YELLOW}⚠️  Missing deprecated field in: $file${NC}"
        WARNINGS=$((WARNINGS + 1))
    fi
}

# Check all YAML files for deprecation and version issues
echo "Checking YAML files for deprecation and version consistency..."

find . -name "*.yaml" -o -name "*.yml" | while read -r file; do
    # Skip .git directories
    if [[ "$file" == *"/.git/"* ]]; then
        continue
    fi

    check_deprecated_yaml "$file"
    check_version_consistency "$file"
done

# Check for scripts with deprecated status
echo "Checking scripts for deprecation markers..."

find . -name "*.py" -o -name "*.sh" | while read -r file; do
    # Skip .git directories
    if [[ "$file" == *"/.git/"* ]]; then
        continue
    fi

    if grep -q "# DEPRECATED\|# deprecated\|deprecated: true" "$file"; then
        echo -e "${YELLOW}⚠️  Found deprecated script: $file${NC}"
        DEPRECATED_COUNT=$((DEPRECATED_COUNT + 1))
    fi
done

# Check for expired versions based on dates
echo "Checking for potentially expired versions..."

current_date=$(date +%Y-%m-%d)
find . -name "*.yaml" -o -name "*.yml" | while read -r file; do
    # Skip .git directories
    if [[ "$file" == *"/.git/"* ]]; then
        continue
    fi

    # Extract date if present
    if file_date=$(grep "date:" "$file" | head -1 | sed 's/.*date: *"*\([0-9-]*\)"*.*/\1/'); then
        if [[ -n "$file_date" && "$file_date" < "2024-01-01" ]]; then
            echo -e "${YELLOW}⚠️  Old date found in: $file (date: $file_date)${NC}"
            WARNINGS=$((WARNINGS + 1))
        fi
    fi
done

# Summary
echo ""
echo "📊 Deprecation Check Summary:"
echo "   Deprecated items found: $DEPRECATED_COUNT"
echo "   Version issues: $VERSION_ISSUES"
echo "   Warnings: $WARNINGS"

# Exit with error if critical issues found
if [ $VERSION_ISSUES -gt 0 ]; then
    echo -e "${RED}❌ Critical deprecation/version issues found. Please fix before committing.${NC}"
    exit 1
fi

if [ $DEPRECATED_COUNT -gt 0 ] || [ $WARNINGS -gt 0 ]; then
    echo -e "${YELLOW}⚠️  Deprecation warnings found. Consider addressing before committing.${NC}"
fi

echo -e "${GREEN}✅ Deprecation check completed${NC}"
exit 0