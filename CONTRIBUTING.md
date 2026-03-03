# Contributing to SSID

## Principles

1. **Deterministic gates are mandatory.** Every change must pass the full gate chain before merge.
2. **No autonomous write access.** Automated workers (LLM agents, CI bots) may propose patches and plans. They have no merge authority without human review.
3. **Hash-only evidence.** No agent stdout, stderr, or prompts are persisted in the repository. Only cryptographic hashes and metadata are retained as audit evidence.
4. **Vendor-neutral.** References to specific LLM providers, API keys, or proprietary tooling are not permitted in committed code or documentation.

## Workflow

```
1. Create or pick a task
2. Run the dispatcher:          python 12_tooling/cli/ssid_dispatcher.py
3. Implement changes
4. Run gates locally:           python 12_tooling/cli/run_all_gates.py
5. Validate SoT:                python 12_tooling/cli/sot_validator.py --verify-all
6. Check for drift:             python 12_tooling/cli/sot_diff_alert.py
7. Submit PR (gates run in CI, blocking)
```

## Gate Chain

All gates must pass. Order matters.

1. **Git Worktree Check** — verify we are inside a valid git repository
2. **Structure Guard** — enforce ROOT-24-LOCK (24 modules, no unauthorized root items)
3. **Sandbox Hygiene** — ensure `.ssid_sandbox/` is gitignored and not tracked
4. **Repo Separation Guard** — prevent cross-repo contamination
5. **Duplicate Guard** — detect duplicated files
6. **OPA Policy** — evaluate compliance policies
7. **SoT Validator** — verify all Source-of-Truth rules
8. **QA Master Suite** — run quality checks in minimal mode (hash + summary only)

## Root-Level Policy (ROOT-24-LOCK)

The repository root is strictly controlled. Only 24 numbered modules and explicitly allowed exceptions may exist at root level.

- Allowed exceptions are defined in `23_compliance/exceptions/root_level_exceptions.yaml`
- Every new root exception requires an Architecture Decision Record (ADR) in `16_codex/decisions/`
- The structure guard (`12_tooling/scripts/structure_guard.py`) enforces this policy

## Architecture Decisions

All significant decisions are documented as ADRs in `16_codex/decisions/ADR_*.md`.
Before proposing a structural change, check existing ADRs for context.

## Security

- Never commit secrets, keys, tokens, or PII.
- `.claude/` is local-only and gitignored (see ADR-0005).
- Report vulnerabilities via GitHub Security Advisories, not public issues.
