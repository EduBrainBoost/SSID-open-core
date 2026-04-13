#!/usr/bin/env bash
# Generate SHA256 lock files for critical SSID artifacts
# Usage: bash 12_tooling/scripts/gen_sha256_locks.sh
set -euo pipefail

CRITICAL_FILES=(
  "24_meta_orchestration/registry/registry.yaml"
  "23_compliance/policies/structure_policy.yaml"
  "23_compliance/exceptions/structure_exceptions.yaml"
  "12_tooling/scripts/structure_guard.sh"
  "24_meta_orchestration/triggers/ci/gates/structure_lock_l3.py"
)

for f in "${CRITICAL_FILES[@]}"; do
  if [ -f "$f" ]; then
    sha256sum "$f" | awk '{print $1}' > "${f}.lock"
    echo "LOCKED: $f -> $(cat ${f}.lock)"
  else
    echo "SKIP: $f (not found)"
  fi
done
echo "SHA256 lock generation complete."
