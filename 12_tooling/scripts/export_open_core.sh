#!/usr/bin/env bash
# export_open_core.sh — OpenCore Export wrapper (SoT-aligned)
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
python "$REPO_ROOT/12_tooling/scripts/export_opencore_filtered.py" \
  --repo-root "$REPO_ROOT" \
  --output-dir "$REPO_ROOT/23_compliance/evidence/exports" \
  "$@"
