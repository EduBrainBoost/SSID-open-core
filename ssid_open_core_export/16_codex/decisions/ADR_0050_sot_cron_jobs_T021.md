# ADR-0050: SoT Cron Jobs Implementation (T-021)

Date: 2026-03-01
Status: Accepted
Decider: EduBrainBoost

## Context
Master Definition v1.1.1 (Lines 1015-1017) defines 2 mandatory cron schedules. Schutzreport defines a 3rd. All 3 were MISSING from .github/workflows/.

## Decision
Add 3 new workflow files implementing exactly the SoT-defined schedules:
- cron_daily_sanctions.yml (15 3 * * *)
- cron_quarterly_audit.yml (0 0 1 */3 *)
- cron_daily_structure_gate.yml (0 2 * * *)

File-based delivery via 02_audit_logging/logs/cron_runs.jsonl (WORM). No chat channel required.

## Consequences
- All 3 SoT cron jobs now implemented and auditable
- WORM log ensures evidence trail per run
- SHA256 manifest per run via cron_sha256_manifest.py

## Guards
ROOT-24-LOCK: unchanged | SAFE-FIX: additive only | PR-only
