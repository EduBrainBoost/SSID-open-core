# ADR-0076: Dual Governance Pattern Clarification

**Status:** PROPOSED
**Date:** 2026-03-30
**Author:** Governance Compliance Agent
**Triggered by:** Token/DAO Audit (7b305d1b) — Finding OBS-01

## Context

The SSID governance layer currently implements two distinct voting patterns
that coexist in the smart-contract stack:

1. **SSIDGovernor** — Token-weighted governance (ERC-20 / ERC-721 based).
   Voting power is proportional to the number of SSID governance tokens held
   or delegated by a participant. This follows the OpenZeppelin Governor pattern.

2. **MarketDAOVote** — One-address-one-vote governance.
   Each verified address receives exactly one vote, regardless of token holdings.
   This pattern prioritizes democratic equality over economic stake.

Audit finding OBS-01 noted that the coexistence of both patterns without a
clear decision record creates ambiguity about which pattern applies in which
context. This ADR resolves that ambiguity.

## Decision

Both patterns are retained. Their applicability is scoped as follows:

### SSIDGovernor (Token-Weighted)

Use when the decision affects:

- Protocol-level parameter changes (fee structures, staking thresholds)
- Treasury allocation and budget proposals
- Smart contract upgrades requiring economic alignment
- Infrastructure investment decisions

**Rationale:** Participants with larger economic exposure should have
proportional influence over decisions that directly affect protocol economics.

### MarketDAOVote (One-Address-One-Vote)

Use when the decision affects:

- Community standards and code-of-conduct changes
- Onboarding and identity verification policy
- Dispute resolution and appeals
- Feature prioritization in the public roadmap
- Compliance policy amendments

**Rationale:** Identity and community governance decisions must not be
plutocratic. Every verified participant has equal standing in matters
that affect fundamental rights and participation rules.

### Hybrid Quorum (Future Extension)

For decisions that span both scopes (e.g., a fee change that also alters
onboarding requirements), a hybrid quorum is recommended:

- Both SSIDGovernor AND MarketDAOVote must independently reach quorum
- The proposal passes only if approved by both mechanisms
- Implementation details are deferred to a follow-up ADR

## Consequences

- All future governance proposals MUST declare which pattern applies
- Smart contract interfaces must expose a `governanceMode` enum:
  `TOKEN_WEIGHTED | ONE_ADDRESS_ONE_VOTE | HYBRID`
- The governance documentation in `07_governance_legal/` must be updated
  to reference this ADR
- Audit teams can verify compliance by checking the declared mode against
  the proposal category

## References

- Token/DAO Audit commit: 7b305d1b
- Finding: OBS-01 (Dual Governance Patterns)
- OpenZeppelin Governor: https://docs.openzeppelin.com/contracts/governance
- 07_governance_legal/ — Governance policy root
- 03_core/ — SSIDGovernor contract source
