#!/usr/bin/env bash
# commit_and_push.sh -- Safe commit wrapper with pre-flight checks.
# Usage: ./12_tooling/scripts/commit_and_push.sh "commit message"
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

MSG="${1:?Usage: commit_and_push.sh \"commit message\"}"

echo "[preflight] Running sot_validator..."
python 12_tooling/cli/sot_validator.py --verify-all || { echo "FAIL: sot_validator"; exit 1; }

echo "[preflight] Running structure gates..."
python 12_tooling/scripts/run_structure_gates.py || { echo "FAIL: structure gates"; exit 1; }

echo "[commit] Staging and committing..."
git add -A
git commit -m "$MSG"

echo "[push] Pushing to origin..."
git push

echo "[done] Commit and push complete."
