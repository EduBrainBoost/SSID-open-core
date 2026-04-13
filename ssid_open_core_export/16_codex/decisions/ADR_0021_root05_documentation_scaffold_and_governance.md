# ADR-0021: Root05 Documentation Scaffold and Governance

## Status
Accepted

## Date
2026-02-28

## Context
Module `05_documentation` (Documentation & Architecture Decisions) serves as
the central documentation hub housing ADRs, security documentation, and legacy
reference material. Despite its critical role in architecture governance, it
lacked the standardized MUST structure (module.yaml, README.md, docs/, src/,
tests/, config/) and had no dedicated governance rules enforcing its
conformance. All 16 shard chart.yaml files had empty interfaces arrays.

## Decision
1. **B1a Scaffold**: Created `module.yaml` (Public Reference,
   architecture_documentation), `README.md`, and four MUST directories
   (docs, src, tests, config). Wired 16 shard `chart.yaml` interfaces
   to central targets (`17_observability/logs/documentation`,
   `23_compliance/evidence/documentation`). Created central log and evidence
   target directories.

2. **B1b Governance**: Added SOT_AGENT_018 (structure), SOT_AGENT_019
   (shadow-file guard), SOT_AGENT_020 (interface wiring) to the validator,
   contract, REGO policy, and registry manifest. Added 7 new tests and the
   `_create_root05_structure()` test helper.

3. **Phase C**: Rehashed 4/6 SoT artifacts in `sot_registry.json`. Created
   WORM evidence manifest (22 artifacts) and audit report.

## Consequences
- `05_documentation` now conforms to SoT v4.1.0 MUST requirements
- 20 governance rules enforced (SOT_AGENT_001..020) across 5 root modules
- Test suite expanded to 136 passing tests (6 skipped)
- Changes touch `24_meta_orchestration/` (registry manifest + sot_registry),
  triggering ADR-Pflicht via Repo Separation Guard

## Affected Modules
- `05_documentation` (primary)
- `24_meta_orchestration` (registry)
- `16_codex` (contract)
- `23_compliance` (REGO policy)
- `11_test_simulation` (tests)
- `02_audit_logging` (WORM evidence + audit report)
- `03_core` (validator source)
- `17_observability` (log target)
