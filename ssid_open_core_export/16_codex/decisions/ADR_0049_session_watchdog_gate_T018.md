# ADR-0049: Session Watchdog Gate (T-018)

Date: 2026-03-01
Status: Accepted
Decider: EduBrainBoost

## Context
T-018 adds a session watchdog gate to detect orphaned agent sessions and enforce hard TTL of 65 minutes. This requires a new CI stage in gates.yml.

## Decision
Add `session_watchdog.py` with hard TTL 65min, orphan-kill, lock-file, SHA256 logging. Add Session Integrity Check stage to gates.yml additively (no existing stages modified).

## Consequences
- CI gains session integrity enforcement
- Orphaned sessions detected and killed automatically
- All existing gates unaffected (additive only)

## Guards
ROOT-24-LOCK: unchanged | SAFE-FIX: additive only | PR-only
