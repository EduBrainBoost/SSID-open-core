# ADR 0011: Runbook Documentation Standards

## Status
Accepted

## Date
2026-02-27

## Context
The automation loop and stability gate runbooks lacked quick-reference
1-command examples and comprehensive troubleshooting sections. The task
orchestration README under `24_meta_orchestration/tasks/` had no getting-started
guide or example TaskSpec, making onboarding difficult for new contributors.

## Decision
1. Standardize runbooks with a Quick Reference section containing 1-command
   copy-paste examples for common operations.
2. Add Pre-flight Checklist sections to runbooks for operator readiness.
3. Expand troubleshooting tables to cover all common failure modes (12+ rows).
4. Add a Getting Started guide and example TaskSpec to the tasks README.
5. Runbook changes are documentation-only and do not modify production code.

## Consequences
- Lower onboarding friction for new contributors and operators.
- Consistent documentation structure across all runbooks.
- Task orchestration README serves as entry point for the TaskSpec workflow.
