# ProofRegistry Contract Specification

## Purpose

Minimal hash-only proof registry for the SSID testnet MVP. Stores SHA256 proof
hashes on-chain with immutable append-only semantics.

## Interface

### Functions

- `addProof(bytes32 proof)` — Store a proof hash. Emits `ProofAdded` event.
  Idempotent: re-adding an existing proof is a no-op (no revert).
- `hasProof(bytes32 proof) view returns (bool)` — Check if a proof hash exists.

### Events

- `ProofAdded(bytes32 indexed proof)` — Emitted when a new proof is stored.

## Storage

- `mapping(bytes32 => bool)` — Single slot per proof hash. No deletion.

## Security Properties

- **Append-only**: No delete or update functions exist.
- **Non-custodial**: Contract holds no native tokens. No `payable` functions.
- **Permissionless**: Any address can add proofs. No owner or access control.
- **Deterministic**: Same input always produces same state transition.

## Compilation

- Compiler: solc 0.8.29
- EVM target: cancun
- Optimization: enabled, 200 runs
- No source `.sol` files in repository (governance policy)

## Deployment

See `12_tooling/testnet_mvp/01_hash_only_proof_registry/scripts/deploy_testnet.py`.
Requires environment variables: `RPC_URL`, `PRIVATE_KEY`, `CHAIN_ID`.
