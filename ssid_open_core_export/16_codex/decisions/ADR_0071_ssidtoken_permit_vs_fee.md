# ADR-0071: SSIDToken Contract Selection — Permit vs Fee Version

| Field       | Value                                      |
|-------------|--------------------------------------------|
| **Status**  | PROPOSED (requires governance approval)    |
| **Date**    | 2026-03-29                                 |
| **Author**  | Governance Audit G05                       |
| **Scope**   | 20_foundation, tokenomics, smart contracts |

---

## Context

The forensic audit (G05: SSIDToken Dual Version) discovered **two separate SSIDToken Solidity contracts** in the repository with divergent designs, licenses, and fee models. Both compile against OpenZeppelin ^0.8.20 and share the same token name ("SSID Token") and symbol ("SSID"), but they are architecturally incompatible. Deploying or referencing both without a canonical designation creates ambiguity for integrators, auditors, and downstream contracts.

### Contract Inventory

| Property                | Permit-Version (SSIDToken.sol)                                      | Fee-Version (SSIDTokenFee.sol)                                              |
|-------------------------|---------------------------------------------------------------------|-----------------------------------------------------------------------------|
| **Path**                | `20_foundation/tokenomics/contracts/SSIDToken.sol`                  | `20_foundation/hardhat/contracts/governance/SSIDTokenFee.sol`               |
| **License**             | MIT                                                                 | Apache-2.0                                                                  |
| **Inheritance**         | ERC20, ERC20Burnable, ERC20Pausable, AccessControl                  | ERC20, Ownable                                                              |
| **Supply Model**        | Mint-on-demand up to MAX_SUPPLY (1B), no pre-mint                   | Full pre-mint of TOTAL_SUPPLY (1B) to deployer                              |
| **Fee Model**           | None — pure utility token                                           | 3% verification fee (1% dev reward, 2% treasury, 50% treasury burn)        |
| **Burn Mechanism**      | ERC20Burnable (voluntary)                                           | Automatic burn via fee with daily (0.5%) and monthly (2%) caps              |
| **Pause Capability**    | Yes (PAUSER_ROLE via AccessControl)                                 | No                                                                          |
| **Access Control**      | OpenZeppelin AccessControl (MINTER_ROLE, PAUSER_ROLE, DEFAULT_ADMIN)| Ownable (single owner, transferToDAO one-way)                               |
| **EIP-2612 Permit**     | Yes (PERMIT_TYPEHASH, DOMAIN_SEPARATOR, nonces)                     | No                                                                          |
| **MiCA Compliance Note**| Explicit disclaimer: no redemption, no yield, no profit distribution| Not stated                                                                  |
| **DAO Transfer**        | Via role grant                                                      | Explicit `transferToDAO()` one-way function                                 |
| **SoT Reference**       | None                                                                | `SSID_structure_gebuehren_abo_modelle.md` (Tier-0)                          |

---

## Decision Drivers

1. **License compatibility** — MIT is strictly more permissive than Apache-2.0; downstream integrators face fewer constraints.
2. **Separation of concerns** — Embedding fee logic directly in the ERC-20 token contract couples token transfer semantics with business logic.
3. **Upgradability** — Fee parameters (rates, caps, recipients) are hardcoded as constants in SSIDTokenFee.sol, requiring redeployment for any change.
4. **Role granularity** — AccessControl (Permit-Version) provides fine-grained multi-role governance; Ownable (Fee-Version) is single-owner.
5. **EIP-2612 Permit** — Gasless approvals are increasingly standard for DeFi and wallet UX.
6. **MiCA risk** — The Permit-Version explicitly disclaims yield/profit characteristics, reducing regulatory surface.
7. **Audit scope** — A simpler base token with external fee routing reduces the attack surface of the core token contract.

---

## Options

### Option A: Permit-Version as L0 Canonical + IdentityFeeRouter (RECOMMENDED)

- **SSIDToken.sol** (Permit-Version) becomes the single canonical ERC-20 token contract.
- Fee collection, dev rewards, treasury distribution, and burn logic are extracted into a separate **IdentityFeeRouter** contract.
- The router calls `transferFrom` (using Permit for gasless UX) and `burn` on the canonical token.
- Fee parameters become upgradeable via governance (proxy or parameter contract) without redeploying the token.
- SSIDTokenFee.sol is archived to `16_codex/archive/` with a deprecation notice.

**Pros:**
- Clean separation: token is token, fees are fees.
- MIT license — maximum downstream freedom.
- EIP-2612 Permit support built in.
- AccessControl supports multi-role DAO governance.
- Pause capability for emergency response.
- MiCA disclaimer preserved.
- Fee logic upgradeable independently.

**Cons:**
- Requires building the IdentityFeeRouter contract.
- Two contracts to audit instead of one monolith.

### Option B: Fee-Version as Canonical + Add Permit Support

- **SSIDTokenFee.sol** becomes canonical, extended with EIP-2612 Permit and AccessControl.
- Requires license change negotiation (Apache-2.0 to MIT) or dual-license.
- Requires adding Pausable, Burnable, and role-based access.

**Pros:**
- Fee logic already implemented and tested.
- Single contract deployment.

**Cons:**
- Significant refactoring needed (Ownable to AccessControl, add Permit, add Pausable).
- Hardcoded fee constants remain non-upgradeable.
- Apache-2.0 license is more restrictive.
- No MiCA compliance disclaimer.
- Tight coupling of fee logic to token transfers.

### Option C: Merge Both into Single Unified Contract

- New contract combining all features from both versions.
- Maximum feature set but maximum complexity.

**Pros:**
- Single source of truth for all token functionality.

**Cons:**
- Largest attack surface.
- Highest audit cost.
- Violates separation of concerns.
- Fee parameter changes still require redeployment unless proxy pattern added.
- Complexity contradicts MiCA risk-reduction strategy.

---

## Recommendation

**Option A — Permit-Version as L0 canonical, fees via IdentityFeeRouter.**

Rationale:
1. The Permit-Version is architecturally cleaner — it follows the ERC-20 standard without embedding business logic.
2. MIT license provides maximum compatibility for ecosystem integrators.
3. Fee logic belongs in a router, not in the token — this allows fee parameter governance without touching the core token contract.
4. EIP-2612 Permit enables gasless approval flows critical for onboarding UX.
5. AccessControl with MINTER/PAUSER/ADMIN roles maps directly to DAO multi-sig governance.
6. The explicit MiCA disclaimer in the Permit-Version reduces regulatory risk.
7. The Fee-Version's SoT reference (`SSID_structure_gebuehren_abo_modelle.md`) defines the fee *model*, not the fee *implementation location* — the model can be implemented in a router contract.

---

## Decision

**PENDING** — Requires architect approval.

### Required Actions Upon Approval
1. Designate `20_foundation/tokenomics/contracts/SSIDToken.sol` as L0 canonical token contract.
2. Create `IdentityFeeRouter.sol` implementing the 3% fee model from `SSID_structure_gebuehren_abo_modelle.md`.
3. Archive `20_foundation/hardhat/contracts/governance/SSIDTokenFee.sol` to `16_codex/archive/SSIDTokenFee.sol.archived` with deprecation notice.
4. Update SoT registry to reflect canonical token path.
5. Add router contract to audit pipeline.

---

## References

- Permit-Version: `20_foundation/tokenomics/contracts/SSIDToken.sol`
- Fee-Version: `20_foundation/hardhat/contracts/governance/SSIDTokenFee.sol`
- Fee Model SoT: `SSID_structure_gebuehren_abo_modelle.md` (Tier-0)
- EIP-2612: https://eips.ethereum.org/EIPS/eip-2612
- OpenZeppelin AccessControl: https://docs.openzeppelin.com/contracts/5.x/access-control
