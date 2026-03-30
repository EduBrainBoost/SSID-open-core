#!/usr/bin/env bash
# CI Guard: token matrix validator — checks token_matrix.yaml against schema
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$REPO_ROOT"

echo "[GUARD] token matrix validator"

VALIDATOR_CONFIG="16_codex/registry/token_matrix_validator.yaml"
if [ ! -f "$VALIDATOR_CONFIG" ]; then
  echo "[FAIL] $VALIDATOR_CONFIG not found"
  exit 1
fi

# Check bool_synonyms uses string keys
if python -c "
import yaml, sys
with open('$VALIDATOR_CONFIG') as f:
    d = yaml.safe_load(f)
bs = d.get('bool_synonyms', {})
if 'true' not in bs or 'false' not in bs:
    print('[FAIL] bool_synonyms missing string keys true/false')
    sys.exit(1)
print('[PASS] token_matrix_validator.yaml schema valid')
" 2>/dev/null; then
  echo "[PASS] token matrix validator"
else
  echo "[FAIL] token matrix validator"
  exit 1
fi
