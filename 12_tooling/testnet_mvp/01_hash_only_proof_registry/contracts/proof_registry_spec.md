# ProofRegistry Contract Specification

> Derived from `24_meta_orchestration/contracts/proof_registry_spec.md` (canonical SoT).

## Overview

| Field         | Value                                           |
|---------------|-------------------------------------------------|
| Contract Name | ProofRegistry                                   |
| Solidity      | 0.8.29                                          |
| EVM Target    | cancun                                          |
| Purpose       | Hash-only proof storage for SSID testnet MVP    |
| PII Stored    | None                                            |
| Secrets       | None                                            |

## Purpose

ProofRegistry is a minimal on-chain contract for the SSID Testnet MVP.
It stores **only cryptographic proof hashes** (bytes32) -- never raw data,
PII, or secrets. Any party can submit a proof hash and later verify its
existence on-chain.

## Interface

### Functions

#### `addProof(bytes32 proof) external`

Stores a proof hash on-chain. Idempotent: re-adding an existing proof
is a no-op (no revert).

Emits `ProofAdded(proof)` on success (first add only).

#### `hasProof(bytes32 proof) external view returns (bool)`

Returns `true` if the proof hash has been previously stored via
`addProof`, `false` otherwise. Read-only, costs no gas.

### Events

#### `ProofAdded(bytes32 indexed proof)`

Emitted when a new proof hash is successfully stored.

- `proof` -- the bytes32 hash that was stored (indexed for log filtering)

## Storage Layout

| Slot | Type                     | Description              |
|------|--------------------------|--------------------------|
| 0    | mapping(bytes32 => bool) | proof hashes             |

A single mapping. No arrays, no structs, no upgradeable proxy patterns.

## Security Considerations

1. **Idempotent**: Re-adding an existing proof is a no-op. No revert.
2. **No access control**: Any address can call `addProof`. This is
   intentional for the testnet MVP -- permissionless proof submission.
3. **No deletion**: Once a proof is stored it cannot be removed.
   Immutability is a feature for tamper-evident audit trails.
4. **Hash-only**: The contract stores only `bytes32` hashes. No PII,
   no plaintext data, no key material ever touches this contract.
5. **No upgradeability**: The contract has no proxy, no admin, and no
   `selfdestruct`. Deployed bytecode is final.

## Canonical Solidity Source

The authoritative source is embedded below. **No `.sol` file is committed
to the repository.** Compilation is performed externally (Remix, Hardhat,
or Foundry) and only the resulting artifacts (ABI, bytecode) are stored.

```solidity
// SPDX-License-Identifier: MIT
pragma solidity 0.8.29;

contract ProofRegistry {
    mapping(bytes32 => bool) private _proofs;

    event ProofAdded(bytes32 indexed proof);

    function addProof(bytes32 proof) external {
        if (!_proofs[proof]) {
            _proofs[proof] = true;
            emit ProofAdded(proof);
        }
    }

    function hasProof(bytes32 proof) external view returns (bool) {
        return _proofs[proof];
    }
}
```

## Compilation

See `compiler_manifest.json` for exact compiler version, optimization
settings, and integrity hashes of all artifacts.

## Artifact Inventory

| File                          | Description                       |
|-------------------------------|-----------------------------------|
| `proof_registry_abi.json`     | Standard Solidity ABI array       |
| `proof_registry_bytecode.json`| Init bytecode (hex)               |
| `compiler_manifest.json`      | Compiler config and hash manifest |
| `proof_registry_spec.md`      | This specification document       |
