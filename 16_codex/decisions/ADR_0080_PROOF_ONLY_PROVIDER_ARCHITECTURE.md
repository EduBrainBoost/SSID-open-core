# ADR-0080: Proof-Only Provider Architecture

## Status: ACCEPTED

## Date: 2026-03-28

## Context

SSID must not act as payment intermediary, custodian, or KYC operator.
The EU AI Act, eIDAS 2.0, and GDPR require strict separation of
identity verification operations from the platform that consumes the
verification result. Users must maintain control over their identity
data and pay verification providers directly.

The existing KYC provider decision matrix (kyc_provider_registry.json)
established provider rankings but lacked a formal verification engine
and compliance policy enforcement layer.

## Decision

1. **User pays verification provider directly** -- SSID has zero role
   in the payment flow between user and provider.
2. **SSID receives only proof/pass/credential/status** -- no raw PII,
   no biometric data, no identity documents.
3. **Provider registry with capability model** -- each provider declares
   proof_only_mode, payment_flow, revocation support, and jurisdiction
   coverage.
4. **Fail-closed enforcement** -- unknown providers, non-proof-only
   providers, expired proofs, revoked proofs, and banned jurisdictions
   are all rejected.
5. **ProofVerifier engine** in 03_core enforces all rules at runtime.
6. **Compliance policy** (SSID-POV-001) with 7 rules governs the
   entire proof-only flow.

## Providers (initial)

| Provider | Category | Status | Direct Pay |
|----------|----------|--------|------------|
| D-Trust sign-me | QES Certificate | preferred | yes |
| Namirial | Remote Signature | preferred | yes |
| InfoCert | QES Certificate | preferred | yes |
| Quadrata | Web3 Pass | preferred_web3 | yes |
| KILT Protocol | SSI Native | preferred_ssi_native | yes |
| Civic Pass | Web3 Pass | conditional | conditional |
| Yoti | Identity Verification | deprioritized | no (B2B) |
| Blockpass | Identity Verification | deprioritized | no (B2B) |

## Consequences

- No payment logic in SSID codebase
- No PII stored on-chain or off-chain (only SHA3-256 hashes)
- All providers must support proof-only mode to be active
- Jurisdiction blacklist (23_compliance) is enforced at proof verification
- B2B-only providers (Yoti, Blockpass) remain available as fallback but
  are not primary choices for the direct-pay architecture

## Artifacts

- `19_adapters/providers/provider_registry.yaml` -- capability registry
- `03_core/validators/verification/proof_verifier.py` -- verification engine
- `23_compliance/policies/proof_only_verification_policy.yaml` -- policy rules
- `11_test_simulation/tests/unit/test_provider_proof_only.py` -- unit tests
