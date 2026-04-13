# ADR-0022: Root06 Data Pipeline Scaffold and Governance

## Status
Accepted

## Date
2026-02-28

## Context
Module `06_data_pipeline` (Data Pipeline & ETL Operations) manages data
ingestion, transformation, and routing infrastructure across 16 domain shards.
It lacked the standardized MUST structure (module.yaml, README.md, docs/, src/,
tests/, config/) and had no dedicated governance rules enforcing its
conformance. All 16 shard chart.yaml files had empty interfaces arrays.

## Decision
1. **B1a Scaffold**: Created `module.yaml` (Internal Operations,
   data_processing_infrastructure), `README.md`, and four MUST directories
   (docs, src, tests, config). Wired 16 shard `chart.yaml` interfaces
   to central targets (`17_observability/logs/data_pipeline`,
   `23_compliance/evidence/data_pipeline`). Created central log and evidence
   target directories.

2. **B1b Governance**: Added SOT_AGENT_021 (structure), SOT_AGENT_022
   (shadow-file guard), SOT_AGENT_023 (interface wiring) to the validator,
   contract, REGO policy, and registry manifest. Added 7 new tests and the
   `_create_root06_structure()` test helper.

3. **Phase C**: Rehashed 4/6 SoT artifacts in `sot_registry.json`. Created
   WORM evidence manifest and audit report.

## Consequences
- `06_data_pipeline` now conforms to SoT v4.1.0 MUST requirements
- 23 governance rules enforced (SOT_AGENT_001..023) across 6 root modules
- Test suite expanded to 143 passing tests (6 skipped)
- Changes touch `24_meta_orchestration/` (registry manifest + sot_registry),
  triggering ADR-Pflicht via Repo Separation Guard
- Includes linter fix: `sys.modules.pop` cache eviction in test loader

## Affected Modules
- `06_data_pipeline` (primary)
- `24_meta_orchestration` (registry)
- `16_codex` (contract)
- `23_compliance` (REGO policy)
- `11_test_simulation` (tests)
- `02_audit_logging` (WORM evidence + audit report)
- `05_documentation` (this ADR)
- `03_core` (validator source)
- `17_observability` (log target)
