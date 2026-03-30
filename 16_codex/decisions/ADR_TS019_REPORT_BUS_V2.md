# ADR-TS019: Report Bus v2 — Event-Store Model

**Status:** Accepted
**Date:** 2026-03-05
**TaskSpec:** TS019_REPORT_BUS_V2

## Context

The original Report Bus (v1) was an append-only JSONL file with 6 events.
There was no event-store model, no deterministic rebuild, no CI gate,
and no systematic traceability from PR merges to audit events.

130 all-commit backfills from a previous attempt (TS017) introduced noise
without meaningful provenance.

## Decision

1. **Event-store model**: Individual `EVENT_*.json` files in
   `24_meta_orchestration/report_bus/events/` are the source of truth.
   `report_bus.jsonl` is a derived artifact rebuilt deterministically
   (sorted by `observed_utc`, then `event_id`).

2. **Schema v2**: New required fields `event_id` (sha256 of canonical JSON),
   `event_type`, `origin` (observed | constructed | imported).
   Optional: `merge_sha`, `pr_number`, `task_id`, `refs`.

3. **PR-merge-only backfill**: Only the 72 PR-referencing merge commits
   get backfill events (`origin=constructed`). Non-PR commits are excluded
   to avoid provenance noise.

4. **Legacy migration**: 6+1 original events migrated with `origin=imported`,
   original JSONL archived to `02_audit_logging/archives/report_bus_legacy/`.

5. **Agent runs**: Per-merge evidence directories stored under
   `02_audit_logging/agent_runs/run-merge-{sha7}/`.

6. **CI gate**: `.github/workflows/report_bus_gate.yml` runs
   `evidence_chain.py scan --last-merge --require-agent-run --require-report-event`
   on every push to main.

## Consequences

- Every future PR merge must produce a report bus event + agent_run to pass CI.
- `report_bus.py rebuild --verify` is idempotent (rerun produces no diffs).
- Supersedes TS017 (all-commit backfill) and TS018 (gate planning).
