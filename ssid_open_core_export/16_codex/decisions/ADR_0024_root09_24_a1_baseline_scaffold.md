# ADR-0024: Root09–24 A1 Baseline Scaffold

## Status
Accepted

## Date
2026-02-28

## Context
Roots 09–24 lacked the standardized A1 baseline structure (module.yaml,
README.md, docs/, src/, tests/, config/) required for deterministic governance
and future A2 SoT enforcement. Root 08_identity_score was missing its config/
directory. This structural gap prevented uniform CI gate enforcement across
all 24 roots. The change is structural across multiple roots, hence
ADR-Pflicht applies.

## Decision
1. Add A1 baseline artifacts to roots 09–24: module.yaml, README.md, and
   four MUST directories (docs, src, tests, config) with .gitkeep where empty.
2. Add missing config/ directory to root 08_identity_score.
3. All module.yaml files follow the 06_data_pipeline template pattern
   (SoT v4.1.0, ROOT-24-LOCK, classification per module purpose).
4. No changes to SoT-5 artifacts in this PR.
5. Idempotent: no existing files overwritten.

## Consequences
- All 24 roots now have minimum A1 structural parity
- Structural parity enables subsequent per-root A2 SoT enforcement
- CI guards (structure_guard, SoT validator) remain enforceable
- No evidence/WORM artifacts committed
- 97 new files across 17 roots (08–24)

## Affected Modules
- 08_identity_score (config/ added)
- 09_meta_identity through 24_meta_orchestration (full A1 scaffold)
- 05_documentation (this ADR)
