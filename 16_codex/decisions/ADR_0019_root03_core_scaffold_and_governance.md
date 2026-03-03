# ADR-0019: Root03 Core Scaffold and Governance

## Status
Accepted

## Date
2026-02-28

## Context
Module `03_core` (Core Validators & Authority) is the final authority module
in the SSID platform. It houses the master SoT validator, security primitives,
and the central interface bus. Despite its critical role, it lacked the
standardized MUST structure (module.yaml, README.md, docs/, src/, tests/,
config/) and had no dedicated governance rules enforcing its conformance.

## Decision
1. **B1a Scaffold**: Created `module.yaml` (Internal Authority, final_authority),
   `README.md`, and four MUST directories (docs, src, tests, config). Wired
   16 shard `chart.yaml` interfaces to central targets. Created central log
   and evidence targets.

2. **B1b Governance**: Added SOT_AGENT_012 (structure), SOT_AGENT_013
   (shadow-file guard), SOT_AGENT_014 (interface wiring) to the validator,
   contract, REGO policy, and registry manifest. Added 7 new tests and the
   `_create_root03_structure()` test helper.

3. **Phase C**: Rehashed 4/6 SoT artifacts in `sot_registry.json`. Updated
   audit report to reflect all checks PASS.

## Consequences
- `03_core` now conforms to SoT v4.1.0 MUST requirements
- 14 governance rules enforced (SOT_AGENT_001..014) across 3 root modules
- Test suite expanded to 126 passing tests
- Changes touch `24_meta_orchestration/` (registry manifest + sot_registry),
  triggering ADR-Pflicht via Repo Separation Guard

## Affected Modules
- `03_core` (primary)
- `24_meta_orchestration` (registry)
- `16_codex` (contract)
- `23_compliance` (REGO policy)
- `11_test_simulation` (tests)
- `02_audit_logging` (WORM evidence + audit report)
- `05_documentation` (this ADR)
- `17_observability` (log target)
