# ADR-0065: PH3 Polygon Amoy Artifact Alignment + web3 tx Compat

- **Status:** Accepted
- **Date (UTC):** 2026-03-04
- **Scope:** `12_tooling/testnet_mvp/`, `24_meta_orchestration/contracts/`

## Context

Phase 3 Testnet MVP targets Polygon Amoy (chainId 80002) as the deployment
network. The deploy artifacts in `12_tooling/testnet_mvp/` diverged from the
canonical SoT in `24_meta_orchestration/contracts/` (solc 0.8.20/london vs
0.8.29/cancun), causing ABI selector mismatches and `execution reverted` on
verify calls. Additionally, web3.py v6 returns `rawTransaction` (CamelCase)
while v7+ uses `raw_transaction` (snake_case) on `SignedTransaction`.

## Decision

1. Align deploy artifacts (ABI, bytecode, compiler_manifest) to SoT canonical
2. Add `getattr` fallback for `raw_transaction`/`rawTransaction` in deploy and
   verify scripts for web3 v6/v7 compatibility
3. Update TESTNET_RUNBOOK.md from Sepolia/Goerli examples to Polygon Amoy
4. Use chain-agnostic wording in proof_registry_spec.md

## Consequences

- Deploy and verify scripts work with both web3 v6 and v7+
- Artifact drift between deploy and SoT paths is eliminated
- Documentation reflects the actual target network (Polygon Amoy)
