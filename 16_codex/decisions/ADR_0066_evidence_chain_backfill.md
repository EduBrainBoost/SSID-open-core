# ADR-0066: Evidence Chain Backfill (TS017)

**Status**: Accepted
**Date**: 2026-03-05
**Deciders**: System Owner

## Context

Multiple merge commits on `main` lack corresponding audit artifacts:
- `02_audit_logging/agent_runs/` entries (agent run records)
- `02_audit_logging/inbox/report_bus.jsonl` events
- Canonical mapping between TaskSpec, PR, merge SHA, and evidence

This violates the SSID audit policy requiring evidence per merge.

## Decision

Implement a retroactive backfill tool (`evidence_chain.py`) that:

1. Scans git history (first-parent) for all merge commits
2. Generates missing `agent_runs/run-merge-{sha7}/` directories with:
   - `run_manifest.json` (commit metadata)
   - `diff.patch` (first-parent diff)
   - `git_show.txt` (commit header)
   - `attestation.md` (explicit retroactive disclaimer)
3. Generates missing report_bus events as individual JSON files
4. Builds `execution_index.json` mapping commits to TaskSpecs/PRs
5. All artifacts marked `provenance: DERIVED_GIT` (no agent execution claims)

The `repo_separation_guard.py` is updated to allow `run-merge-*` and `backfill/` paths
under `02_audit_logging/agent_runs/` as exceptions to the forbidden path rule.

## Consequences

- Lückenlose Nachweiskette for all historical merges
- Future prevention via TS018 evidence_chain gate (planned)
- No git history rewrites; additive only
- Idempotent: rerun produces no diffs
