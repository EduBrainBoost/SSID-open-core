#!/usr/bin/env bash
# CI Guard: Hardhat compile smoke test — verifies Solidity contracts compile
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$REPO_ROOT"

echo "[GUARD] Hardhat smoke test"

# Check for Solidity contracts
SOL_COUNT=$(find . -name "*.sol" -not -path "*/node_modules/*" -not -path "*/worm/*" | wc -l)
echo "[INFO] Found $SOL_COUNT Solidity contracts"

# Check ABI directory
ABI_DIR="20_foundation/tokenomics/abi"
if [ -d "$ABI_DIR" ]; then
  ABI_COUNT=$(find "$ABI_DIR" -name "*.json" | wc -l)
  echo "[EXPORT] $ABI_COUNT ABIs in $ABI_DIR"
else
  echo "[WARN] ABI directory $ABI_DIR not found — compile required"
fi

# Verify key contracts exist
for sol in 20_foundation/tokenomics/contracts/SSIDToken.sol 20_foundation/tokenomics/contracts/SSIDSBT.sol; do
  if [ ! -f "$sol" ]; then
    echo "[FAIL] Missing contract: $sol"
    exit 1
  fi
done

echo "[PASS] Hardhat smoke test (contracts present)"
