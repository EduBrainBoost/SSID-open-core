#!/usr/bin/env bash
# repo_size_audit.sh - Repository bloat detection and reporting
# SoT Reference: Repo-Bloat-Schutz requirement
# Created: 2026-03-30 by 00_master_orchestrator (GAP-003 fix)

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$REPO_ROOT"

echo "=== SSID Repository Size Audit ==="
echo "Date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo ""

# Total repo size (excluding .git)
echo "--- Repo Size (excluding .git) ---"
du -sh --exclude=.git . 2>/dev/null || du -sh . 2>/dev/null
echo ""

# .git directory size
echo "--- .git Directory Size ---"
du -sh .git 2>/dev/null || echo "N/A"
echo ""

# Top 20 largest files
echo "--- Top 20 Largest Files ---"
find . -not -path './.git/*' -type f -exec ls -la {} \; 2>/dev/null | sort -k5 -rn | head -20
echo ""

# Files over 1MB
echo "--- Files Over 1MB ---"
find . -not -path './.git/*' -type f -size +1M -exec ls -lh {} \; 2>/dev/null
echo ""

# Files over 10MB (WARNING)
echo "--- Files Over 10MB (WARNING) ---"
large_files=$(find . -not -path './.git/*' -type f -size +10M 2>/dev/null)
if [ -n "$large_files" ]; then
    echo "WARNING: Large files detected:"
    echo "$large_files" | while read -r f; do ls -lh "$f" 2>/dev/null; done
else
    echo "No files over 10MB found."
fi
echo ""

# Files over 100MB (BLOCKER)
echo "--- Files Over 100MB (BLOCKER) ---"
blocker_files=$(find . -not -path './.git/*' -type f -size +100M 2>/dev/null)
if [ -n "$blocker_files" ]; then
    echo "BLOCKER: Files over 100MB must be removed or tracked via LFS:"
    echo "$blocker_files" | while read -r f; do ls -lh "$f" 2>/dev/null; done
    exit 1
else
    echo "No files over 100MB. PASS."
fi
echo ""

# Binary files check
echo "--- Binary Files (non-text) ---"
find . -not -path './.git/*' -type f \( -name "*.h5" -o -name "*.pkl" -o -name "*.bin" -o -name "*.tar" -o -name "*.gz" -o -name "*.zip" -o -name "*.whl" -o -name "*.exe" -o -name "*.dll" -o -name "*.so" -o -name "*.dylib" \) 2>/dev/null | head -20
echo ""

echo "=== Audit Complete ==="
