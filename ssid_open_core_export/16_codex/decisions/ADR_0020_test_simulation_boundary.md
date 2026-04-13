# ADR-0020: 11_test_simulation — Governance Classification

**Date**: 2026-04-13  
**Status**: ACCEPTED (Phase 2b)  
**Scope**: Root 11_test_simulation export boundary

## Problem Statement

Root `11_test_simulation` has ambiguous status:
- **Canonical SSID policy**: Listed as DENY ("Test infrastructure, public-safe but not core")
- **SSID-open-core reality**: 229 files present; export tests in `11_test_simulation/tests_export/` (6 files)
- **CI behavior**: public_export_integrity.yml (Zeile 152) runs pytest on `11_test_simulation/tests_export/test_export_pipeline.py`
- **Documentation**: CONTRIBUTING.md claims "only 5 roots accept contributions"; no mention of 11_test_simulation

## Decision

**11_test_simulation is EXCLUDED from export boundary.**

Rationale:
1. **Canonical policy explicit**: Canonical SSID lists "11_test_simulation" as DENY
2. **Test infrastructure**: Contents are implementation-specific to SSID; not part of public API
3. **Public-safe but not core**: Export tests can run locally but shouldn't be part of public artifact
4. **Derivative model**: Open-core is API + tooling (5 roots) + optional test harness, not full test suite

## Implementation

Phase 2b-1:
1. ✓ ADR written (this document)
2. Flag for Phase 3: Remove `11_test_simulation/` contents or move tests to root level
3. Flag for Phase 3: Update public_export_integrity.yml to not reference 11_test_simulation/tests_export/

## Consequences

- **CI Change**: Zeile 152 of public_export_integrity.yml must be removed or refactored
- **Test Location**: Export validation tests move to 12_tooling/tests/export/ (stays in exported root)
- **Content**: 11_test_simulation/ remains as empty scaffold (ROOT-24 consistency)

## Alternative: Include 11_test_simulation

If governance review determines 11_test_simulation should be public:
- Update canonical SSID policy to remove from deny_roots
- Rename to something like `11_public_test_harness` to clarify intent
- Document in 16_codex/EXPORT_BOUNDARY.md why test infrastructure is public

**Current recommendation**: EXCLUDE (follows canonical policy).

---

**References**:  
- Canonical SSID deny_roots: SSID/16_codex/opencore_export_policy.yaml  
- Public export integrity workflow: .github/workflows/public_export_integrity.yml (L152)  
- Next: EXPORT_BOUNDARY.md + Phase 3 test reorganization
