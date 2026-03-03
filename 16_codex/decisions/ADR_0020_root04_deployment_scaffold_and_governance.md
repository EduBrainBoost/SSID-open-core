# ADR-0020: Root04 Deployment Scaffold and Governance

## Status
Accepted

## Date
2026-02-28

## Context
Module `04_deployment` (Deployment & Release Operations) manages release
infrastructure across 16 domain shards. Despite having a complete shard
directory structure, it lacked the standardized MUST structure (module.yaml,
README.md, docs/, src/, tests/, config/) and had no dedicated governance
rules enforcing its conformance. All 16 shard chart.yaml files had empty
interfaces arrays.

## Decision
1. **B1a Scaffold**: Created `module.yaml` (Internal Operations,
   release_infrastructure), `README.md`, and four MUST directories
   (docs, src, tests, config). Wired 16 shard `chart.yaml` interfaces
   to central targets (`17_observability/logs/deployment`,
   `23_compliance/evidence/deployment`). Created central log and evidence
   target directories.

2. **B1b Governance**: Added SOT_AGENT_015 (structure), SOT_AGENT_016
   (shadow-file guard), SOT_AGENT_017 (interface wiring) to the validator,
   contract, REGO policy, and registry manifest. Added 7 new tests and the
   `_create_root04_structure()` test helper.

3. **Phase C**: Rehashed 6 SoT artifacts in `sot_registry.json`. Created
   WORM evidence manifest (24 artifacts) and audit report.

## Consequences
- `04_deployment` now conforms to SoT v4.1.0 MUST requirements
- 17 governance rules enforced (SOT_AGENT_001..017) across 4 root modules
- Test suite expanded to 129 passing tests (6 skipped)
- Changes touch `24_meta_orchestration/` (registry manifest + sot_registry),
  triggering ADR-Pflicht via Repo Separation Guard

## Affected Modules
- `04_deployment` (primary)
- `24_meta_orchestration` (registry)
- `16_codex` (contract)
- `23_compliance` (REGO policy)
- `11_test_simulation` (tests)
- `02_audit_logging` (WORM evidence + audit report)
- `05_documentation` (this ADR)
- `17_observability` (log target)
- `03_core` (validator source)
