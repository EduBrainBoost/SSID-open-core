#!/usr/bin/env bash
# build_public_mirror.sh — Public Mirror dry-run (TMP-only, no push)
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT
echo "[build_public_mirror] Dry-run mirror build in $TMP_DIR"
cp -r "$REPO_ROOT/." "$TMP_DIR/mirror/" 2>/dev/null || rsync -a --exclude='.git' "$REPO_ROOT/" "$TMP_DIR/mirror/"
echo "[build_public_mirror] PASS — TMP-only, no push performed"
