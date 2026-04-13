# ADR-0019: Export Boundary Realignment & Policy Authority

**Date**: 2026-04-13  
**Status**: ACCEPTED (Phase 2a)  
**Scope**: SSID-open-core policy governance

## Problem Statement

On 2026-04-05, SSID-open-core's `16_codex/opencore_export_policy.yaml` was modified to allow all 24 roots to be exported, contradicting the canonical SSID export policy which strictly limits exports to 5 roots (03_core, 12_tooling, 16_codex, 23_compliance, 24_meta_orchestration).

As a result:
- **Policy Conflict**: Two versions of the same file exist with contradictory rules
- **Boundary Ambiguity**: 19 roots marked as "denied" in canonical SSID are present and accessible in open-core
- **Authority Confusion**: SSID-open-core re-declared itself as authoritative, overriding canonical SSID
- **Security Risk**: IP-sensitive (01_ai_layer, 08_identity_score), NDA-dependent (07_governance_legal, 09_meta_identity, 10_interoperability, 19_adapters), and security-critical roots (14_zero_time_auth, 21_post_quantum_crypto) are exported

## Decision

**Canonical SSID is the authoritative source-of-truth (SoT) for export boundary policies.**

SSID-open-core is a **derivative**, not a **full copy**. Therefore:

1. `16_codex/opencore_export_policy.yaml` in SSID-open-core reverts to canonical SSID version
2. Export boundary: 5 roots only (03_core, 12_tooling, 16_codex, 23_compliance, 24_meta_orchestration)
3. All 19 denied roots are evaluated for removal or reclassification via separate ADR
4. CONTRIBUTING.md and README.md updated to reflect canonical policy

## Consequences

- ✓ Policy authority restored to canonical SSID
- ✓ Derivative relationship re-established
- ⚠ 19 roots must be addressed (Phase 2b)
- ⚠ CI gates will initially FAIL until boundary is enforced

## Rationale

1. **Coherence**: Single source of truth reduces governance drift
2. **Security**: Exported roots are vetted by canonical SSID; derivative prevents accidental leaks
3. **Intent**: SSID-open-core was designed as "public API + tooling", not "full canonical copy"
4. **Precedent**: All other governance policies (ROOT-24-LOCK, SAFE-FIX, etc.) reference canonical SSID as SoT

## Options Considered

### Option A (SELECTED): Restore Canonical Policy
- Pro: Single SoT; security; matches original intent
- Con: Requires 19 roots to be removed or reclassified

### Option B: Accept Permissive Policy
- Pro: Simpler maintenance
- Con: Security risk; contradicts canonical; "public-safe" claim becomes unverifiable

### Option C: Explicit Waiver
- Pro: Allows full-copy model if justified
- Con: Requires legal/security approval; removes "derivative" classification

## Implementation

Phase 2a-1: Policy file restored  
Phase 2a-2: ADR written (this document)  
Phase 2b-1: ADR-0020 clarifies 11_test_simulation status  
Phase 2b-2: EXPORT_BOUNDARY.md documents all 19 denied roots + rationale

## Approval

- [ ] SSID Project Lead: Policy alignment approved
- [ ] SSID-open-core Maintainer: Derivative model re-confirmed
- [ ] Compliance Lead: Security implications reviewed

---

**References**:  
- Canonical SSID policy: SSID/16_codex/opencore_export_policy.yaml  
- Previous state: backup_2026_04_13  
- Next: ADR-0020 (11_test_simulation status)
