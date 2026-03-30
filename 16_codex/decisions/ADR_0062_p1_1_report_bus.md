# ADR-0062: P1-1 Report Bus — Canonical Append-Only Event Bus

- **Status:** Accepted
- **Date (UTC):** 2026-03-04
- **Scope:** `12_tooling/cli/report_bus.py`, `02_audit_logging/inbox/`

## Context

The SSID gate chain (`run_all_gates.py`) executes 15+ gates sequentially but only
produces unstructured stdout output. Gate results are not machine-queryable, making
automated evidence collection and cross-run comparison impossible.

Phase 1 requires a canonical event bus that captures every gate/analysis result in
a structured, append-only JSONL format — enabling automated aggregation, evidence
linking, and downstream consumption by the PR integrator and evidence WORM.

## Decision

Implement `12_tooling/cli/report_bus.py` as an append-only event bus:

1. **Canonical Schema**: 8 required fields — `ts_utc`, `repo`, `sha`, `source`,
   `kind`, `severity`, `summary`, `payload`
2. **Inbox**: Append-only JSONL at `02_audit_logging/inbox/report_bus.jsonl`
3. **JSON Schema**: `16_codex/contracts/report_bus/report_bus.schema.json`
4. **Integration**: `run_all_gates.py --report-bus` appends exactly 1 event per run
5. **Stop-on-first-fail**: Bus event written before exit, even on early failure
6. **Ingest Adapters**: Read-only adapters for `e2e_run`, `run_log`, `cron_runs`
7. **Contract**: PASS/FAIL + findings only. No scores. Deterministic JSON.

## Not in P1-1 Scope

- Consolidation / deduplication of existing report formats
- Web UI or dashboard
- Retention/rotation policy for the inbox
- Guard mode exit code 2 (reserved for P1-3)
- Cross-repo event federation (SSID-EMS ↔ SSID)

## Consequences

- All gate/analysis results become machine-queryable via a single JSONL file
- PR integrator can reference structured gate results
- Evidence WORM can hash and index events deterministically
- Existing gate logic unchanged — bus is additive/observational
- Ingest adapters enable backfill from existing E2E reports and cron logs
