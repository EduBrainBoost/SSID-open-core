# Evidence Chain Tooling

Deterministic backfill + scan for SSID audit compliance.

## Purpose

Ensures every merge commit on `main` has:
1. An agent_run record in `02_audit_logging/agent_runs/`
2. A report_bus event in `02_audit_logging/inbox/report_bus.jsonl` (or backfill equivalent)
3. An entry in `24_meta_orchestration/registry/execution_index.json`

## Usage

### Scan (read-only)
```bash
python 12_tooling/cli/evidence_chain.py scan
```

### Backfill (write)
```bash
python 12_tooling/cli/evidence_chain.py backfill --write
```

### Gate mode (CI)
```bash
python 12_tooling/cli/evidence_chain.py scan --last-merge --require-agent-run --require-report-event
```

## Idempotency

Rerun produces no diffs. Filenames are keyed by `merge_sha[:7]`, JSON fields are sorted.

## Constraints

- SAFE-FIX: additive only, no deletions
- ROOT-24-LOCK: only writes to allowed paths
- No secrets in output
- PASS/FAIL only (no scores)
