# ADR 0008: Structure Spec Idempotence

## Status
Accepted

## Context
`python 12_tooling/scripts/deterministic_repo_setup.py phase1` rewrote `24_meta_orchestration/registry/structure_spec.json` on every run due to a volatile timestamp field (`generated_utc`) and unconditional JSON writes.

This violated deterministic no-op behavior and dirtied the repository even when no source-of-truth inputs changed.

## Decision
1. Remove volatile metadata from tracked `structure_spec.json` by omitting `generated_utc` in phase1 output.
2. Make JSON writing no-op aware: only write when rendered JSON content differs byte-for-byte from existing file content.

## Consequences
- Re-running phase1 without input changes is idempotent and keeps the repo clean.
- `structure_spec.json` remains stable and diff-friendly for audits.
- Time-based evidence continues to belong in runtime evidence artefacts, not in tracked registry specs.
