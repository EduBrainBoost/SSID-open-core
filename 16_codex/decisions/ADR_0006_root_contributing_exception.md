# ADR 0006: CONTRIBUTING.md Root-Level Exception

## Status
Accepted

## Date
2026-02-12

## Context
Under ROOT-24-LOCK, every file at repository root requires explicit governance approval.
`CONTRIBUTING.md` is a standard GitHub convention file that defines contribution workflow,
gate chain documentation, and security policies for contributors.

Placing it at root is a GitHub platform requirement: GitHub surfaces `CONTRIBUTING.md`
automatically in issue templates, PR templates, and the repository "Community" tab only
when it resides at the repository root (or `.github/`).

## Decision
1. Allow `CONTRIBUTING.md` as a root-level file exception in `23_compliance/exceptions/root_level_exceptions.yaml`.
2. `CONTRIBUTING.md` MUST remain vendor-neutral (no provider names, API keys, or proprietary tooling references).
3. `CONTRIBUTING.md` MUST NOT contain secrets, operational keys, or agent-specific configuration.
4. Content scope: contribution principles, gate chain order, ROOT-24-LOCK policy, ADR requirement, security guidelines.

## Constraints
- Documentation-only file; no executable content.
- Must be consistent with `16_codex/decisions/` ADRs and `23_compliance/` policies.
- Changes to CONTRIBUTING.md must pass the full gate chain like any other committed file.

## Consequences
1. Root layout gains one additional documentation file (minimal surface increase).
2. Contributors can discover workflow and policies without navigating into subdirectories.
3. GitHub platform features (Community tab, PR guidance) work correctly.
4. No feature behavior is added; this is a documentation and onboarding exception.
