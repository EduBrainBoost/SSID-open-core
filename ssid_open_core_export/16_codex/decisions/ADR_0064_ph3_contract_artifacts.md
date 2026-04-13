# ADR-0064: PH3 Contract Artifacts — ProofRegistry ABI, Bytecode, Manifest

- **Status:** Accepted
- **Date (UTC):** 2026-03-04
- **Scope:** `24_meta_orchestration/contracts/`

## Context

Phase 3 (Testnet MVP) requires pre-compiled smart contract artifacts for the
ProofRegistry contract. Per governance policy, no `.sol` source files are
committed to the repository. Only ABI, bytecode, compiler manifest, and
human-readable specification are stored.

## Decision

Add four artifacts to `24_meta_orchestration/contracts/`:
- `proof_registry_abi.json` — Standard Solidity ABI (addProof, hasProof, ProofAdded)
- `proof_registry_bytecode.json` — Compiled bytecode (solc 0.8.29, cancun, opt 200)
- `compiler_manifest.json` — Compiler settings + SHA256 hashes of ABI and bytecode
- `proof_registry_spec.md` — Human-readable contract specification

## Consequences

- Deploy and verify scripts can consume artifacts without external compilation
- Deterministic hashes in compiler_manifest.json ensure reproducibility
- No `.sol` files in repository (enforced by existing gates)
