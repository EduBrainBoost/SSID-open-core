# ADR-0065: PH3 Artifact Alignment — Single Canonical Set (SoT)

- **Status:** Accepted
- **Date (UTC):** 2026-03-04
- **Scope:** `24_meta_orchestration/contracts/`, `12_tooling/testnet_mvp/01_hash_only_proof_registry/`
- **Supersedes:** None (extends ADR-0064)

## Context

Code review of PH3_IMPL_SCRIPTS_002 identified divergent contract artifact
sets between the canonical SoT (`24_meta_orchestration/contracts/`) and the
deploy-side copy (`12_tooling/testnet_mvp/.../contracts/`):

| Aspect           | SoT (24_meta)     | Deploy (12_tooling)          |
|------------------|-------------------|------------------------------|
| solc             | 0.8.29            | 0.8.20                       |
| EVM target       | cancun            | london                       |
| Bytecode key     | `object`          | `bytecode` + `deployedBytecode` |
| ABI members      | 3                 | 4 (extra `proofs()` getter)  |
| ProofAdded event | 1 param           | 3 params                     |
| addProof         | idempotent        | reverts on duplicate         |

The deploy script (`deploy_testnet.py`) had a hard-coded `bytecode_data["bytecode"]`
key lookup that would KeyError after alignment to SoT format.

## Decision

1. **24_meta_orchestration/contracts/ is the single canonical Source of Truth.**
   Deploy-side artifacts are derived copies that must match SoT.
2. **Bytecode loader is key-tolerant:** accepts both `object` and `bytecode` keys.
3. **Drift is CI-gated:** `test_artifact_drift.py` (7 tests) fails on any
   divergence between SoT and deploy artifacts.

## Consequences

- One compiler pin (solc 0.8.29, cancun) across all artifact locations
- ABI/event signatures are consistent (addProof, hasProof, ProofAdded(bytes32))
- Future artifact updates must go through SoT first, then propagate to deploy
- CI catches drift automatically via pytest (no workflow changes needed)
