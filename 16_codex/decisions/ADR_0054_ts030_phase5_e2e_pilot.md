# ADR-0053: TS030 Phase 5 — E2E Pilot Pipeline (Dispatcher + Reports + Gates)

Date: 2026-03-02
Status: Accepted
Decider: EduBrainBoost

## Context
Phase 2 (ADR-0052) established the shards registry and pilot indices. Phase 5
requires a live E2E pipeline: task queue, dispatcher run-task subcommand,
deterministic report generation, and CI-integrated E2E gates.

## Decision
Add:
- `24_meta_orchestration/queue/tasks/PILOT_TASK_0001.yaml` — pilot task definition
- `24_meta_orchestration/queue/inputs/INPUT_DESC_PILOT_0001.json` — input descriptor
- `24_meta_orchestration/dispatcher/e2e_dispatcher.py` (additive `run-task` subcommand)
- `12_tooling/cli/_lib/run_id.py` — deterministic run_id computation
- `12_tooling/cli/shards_registry_build.py` — extended with `--source`, `--deterministic`
- Per-shard index files upgraded to TS030 schema (shard_id, specs with sha256, fixtures with expect)
- 4 E2E gates in `run_all_gates.py`: pipeline smoke, report schema, no-PII, determinism
- `--e2e-only` and `--source` flags for `run_all_gates.py`
- `11_test_simulation/tests_compliance/test_e2e_report_schema.py` (5 tests)
- `02_audit_logging/archives/qa_master_suite/test_e2e_pilot_dispatcher.py` (7 tests)
- `.github/workflows/sot_autopilot.yml` updated with push/PR triggers and E2E steps

## Consequences
- E2E pipeline is live: task YAML triggers dispatcher, produces deterministic reports
- Reports (E2E_RUN, RUN_LOG, E2E_ARTIFACT_HASHES) are hash-only, no PII, no scores
- CI runs E2E gates on every push/PR to main
- Gate chain order: Policy -> SoT -> Shard -> Conformance -> Evidence -> E2E -> QA
