# ADR-0062: Guard mode soft/hard toggle via SSID_GUARD_MODE

- **Status:** Accepted
- **Date (UTC):** 2026-03-04
- **Scope:** `12_tooling/cli/`, `.github/workflows/`

## Context

Guards in run_all_gates.py have a single failure mode (exit 1). CI needs hard enforcement
(exit 2, break the job) while local development needs soft mode (warn, don't block).

## Decision

Add `SSID_GUARD_MODE` environment variable with three values:
- `off`: skip all guards, exit 0
- `soft` (default): run guards, log WARN on failure, exit 0
- `hard`: run guards, log ERROR on failure, exit 2

CI workflows set `SSID_GUARD_MODE=hard` explicitly.

## Consequences

- CI gate failures now exit 2 (deterministic, distinguishable from tooling errors)
- Local development is unblocked by default (soft mode)
- No changes to EMS guard infrastructure (separate SSIDCTL_GUARD_HARD)
