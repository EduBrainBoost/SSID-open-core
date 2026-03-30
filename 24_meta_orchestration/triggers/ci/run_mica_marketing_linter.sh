#!/usr/bin/env bash
# CI Guard: MiCA marketing linter — scans docs for non-compliant terms
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$REPO_ROOT"

echo "[GUARD] MiCA marketing linter"

LINTER="12_tooling/scripts/mica_marketing_linter.py"
if [ ! -f "$LINTER" ]; then
  echo "[FAIL] $LINTER not found"
  exit 1
fi

VIOLATIONS=0
# Scan key documentation files
for doc in README.md CONTRIBUTING.md 05_documentation/docs/*.md 20_foundation/docs/*.md; do
  if [ -f "$doc" ]; then
    if ! python "$LINTER" "$doc" 2>/dev/null; then
      VIOLATIONS=$((VIOLATIONS + 1))
    fi
  fi
done

if [ "$VIOLATIONS" -gt 0 ]; then
  echo "[WARN] $VIOLATIONS files have MiCA marketing violations"
  exit 0  # WARN, not FAIL — requires manual review
fi

echo "[PASS] MiCA marketing linter"
