#!/usr/bin/env bash
# ssid_opencore_push_gate.sh — Push Gate validation (no actual push)
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
echo "[push_gate] Running Secret Scan..."
if git -C "$REPO_ROOT" grep -rn "BEGIN PRIVATE KEY\|AKIA[0-9A-Z]\{16\}\|ghp_" -- . 2>/dev/null | grep -v ".gitignore"; then
  echo "[push_gate] FAIL — secrets detected"
  exit 1
fi
echo "[push_gate] Secret scan: PASS"
echo "[push_gate] Checking manifest..."
MANIFEST="$REPO_ROOT/23_compliance/evidence/exports"
if ls "$MANIFEST"/*.evidence.json 1>/dev/null 2>&1; then
  echo "[push_gate] Manifest: PASS"
else
  echo "[push_gate] WARN — no evidence manifest found"
fi
echo "[push_gate] PASS — gate validated, no push performed"
