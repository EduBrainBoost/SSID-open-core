# R004: NFT Licensing System Status

**Last Updated:** 2026-03-28
**Roadmap Item:** R004
**Overall Status:** PARTIAL -- Contracts exist, deployment pending

---

## Contract Inventory

### SSIDToken.sol

- **Status:** EXISTS
- **Path:** `20_foundation/hardhat/contracts/tokenomics/SSIDToken.sol`
- **ABI:** `20_foundation/hardhat/abi/SSIDToken.abi.json`
- **Compiled Artefacts:** `20_foundation/hardhat/artifacts/contracts/tokenomics/SSIDToken.sol/`
- **Features:**
  - ERC-20 compliant
  - EIP-2612 permit (gasless approvals) support
  - Core utility token for SSID ecosystem
- **Deployment:** Not yet deployed to mainnet

### SSIDSBT.sol

- **Status:** EXISTS
- **Path:** `20_foundation/hardhat/contracts/tokenomics/SSIDSBT.sol`
- **ABI:** `20_foundation/hardhat/abi/SSIDSBT.abi.json`
- **Compiled Artefacts:** `20_foundation/hardhat/artifacts/contracts/tokenomics/SSIDSBT.sol/`
- **Features:**
  - Soulbound token (non-transferable)
  - Badge/credential issuance
  - Identity-linked NFT mechanism
- **Deployment:** Not yet deployed to mainnet

### IAccessGate.sol

- **Status:** EXISTS
- **Path:** `20_foundation/hardhat/contracts/tokenomics/IAccessGate.sol`
- **Features:**
  - Interface for token-gated access control
  - Used by license enforcement layer
- **Deployment:** Interface only, implemented by consuming contracts

### LicenseRegistry.sol

- **Status:** BEING CREATED
- **Planned Path:** `20_foundation/hardhat/contracts/core/LicenseRegistry.sol`
- **Purpose:**
  - On-chain registry mapping license tiers to token holdings
  - Links SSIDToken balances to feature access levels
  - Integrates with IAccessGate for enforcement
- **Dependencies:**
  - SSIDToken.sol (token balance queries)
  - IAccessGate.sol (access control interface)
  - FeeDistribution.sol (fee routing for license purchases)
- **Blocking:** Open-core feature gating (Phase 7)

### FeeDistribution.sol

- **Status:** EXISTS
- **Path:** `20_foundation/hardhat/contracts/core/FeeDistribution.sol`
- **ABI:** `20_foundation/hardhat/abi/FeeDistribution.abi.json`
- **Also at:** `03_core/contracts/FeeDistribution.sol` (copy with ABI)
- **Features:**
  - Fee collection and distribution logic
  - Splits fees between protocol treasury, stakers, and validators
  - Integrates with IdentityFeeRouter
- **Deployment:** Not yet deployed to mainnet

### SSIDTokenFee.sol

- **Status:** EXISTS
- **Path:** `20_foundation/hardhat/contracts/governance/SSIDTokenFee.sol`
- **ABI:** `20_foundation/hardhat/abi/SSIDTokenFee.abi.json`
- **Features:**
  - Fee-enabled variant of SSIDToken
  - Automatic fee deduction on transfers
- **Deployment:** Not yet deployed to mainnet

---

## Supporting Infrastructure

| Component | Status | Path |
|---|---|---|
| IdentityFeeRouter.sol | EXISTS | `20_foundation/hardhat/contracts/core/IdentityFeeRouter.sol` |
| CodexRegistry.sol | EXISTS | `20_foundation/hardhat/contracts/core/CodexRegistry.sol` |
| CodexRewardReporter.sol | EXISTS | `20_foundation/hardhat/contracts/core/CodexRewardReporter.sol` |
| SSIDGovernor.sol | EXISTS | `20_foundation/hardhat/contracts/governance/SSIDGovernor.sol` |
| SSIDRegistry.sol | EXISTS | `20_foundation/hardhat/contracts/governance/SSIDRegistry.sol` |
| License fee matrix | EXISTS | `16_codex/license_fee_matrix.yaml`, `23_compliance/license_fee_matrix.yaml` |
| Open-core export policy | EXISTS | `16_codex/opencore_export_policy.yaml` |

---

## Gap Analysis

### Implemented

1. Core token contract (SSIDToken.sol) with EIP-2612
2. Soulbound badge mechanism (SSIDSBT.sol)
3. Fee distribution logic (FeeDistribution.sol)
4. Fee-enabled token variant (SSIDTokenFee.sol)
5. Access gate interface (IAccessGate.sol)
6. Identity fee routing (IdentityFeeRouter.sol)
7. Governance contract (SSIDGovernor.sol)
8. On-chain registry (SSIDRegistry.sol)

### Missing / In Progress

1. **LicenseRegistry.sol** -- On-chain license tier registry (being created)
2. **Deployment scripts** -- Hardhat deployment scripts for testnet/mainnet
3. **Contract audit** -- External security audit not yet completed
4. **Integration tests** -- End-to-end license flow tests
5. **Frontend integration** -- License purchase/management UI (13_ui_layer)

---

## Next Steps

1. Complete LicenseRegistry.sol implementation
2. Write deployment scripts for testnet
3. Run integration test suite covering full license lifecycle
4. Schedule external smart contract audit
5. Testnet deployment and validation
6. Mainnet deployment (Phase 8)
