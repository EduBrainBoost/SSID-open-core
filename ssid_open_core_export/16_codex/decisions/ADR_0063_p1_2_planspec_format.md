# ADR-0063: P1-2 PlanSpec — Multi-Task Plan Specification Format

- **Status:** Accepted
- **Date (UTC):** 2026-03-04
- **Scope:** `24_meta_orchestration/`, `12_tooling/cli/`

## Context

Individual TaskSpecs (`24_meta_orchestration/tasks/specs/*.yaml`) define single-task
scopes, acceptance criteria, and required checks. However, Phase-level execution
(e.g., "Phase 1: P1-3 Guards -> P1-1 Report Bus -> P1-2 PlanSpec") requires
orchestrating multiple TaskSpecs in sequence with defined dependencies.

Currently this sequencing exists only in prose (phase0_summary.md, roadmap docs).
There is no machine-readable format for multi-task plans, making automated
validation, dependency checking, and progress tracking impossible.

## Decision

Define a `PlanSpec` YAML format in `24_meta_orchestration/plans/` that:

1. **Composes** multiple TaskSpec references into an ordered plan
2. **Declares dependencies** between tasks (blocking relationships)
3. **Defines plan-level acceptance criteria** (cross-task verification)
4. **Is validatable** via `planspec_validator.py`:
   - All referenced task_ids resolve to existing TaskSpec files
   - No circular dependencies
   - Required fields present
   - Acceptance criteria non-empty

Schema: `PLANSPEC_SCHEMA.yaml` alongside `TASK_SPEC_MINIMAL.schema.yaml`.

## Consequences

- Phase-level plans become executable and validatable
- Dispatcher can consume PlanSpecs for multi-task orchestration
- Progress tracking is machine-readable (which tasks in a plan are done)
- Existing TaskSpec format is unchanged — PlanSpec is additive
