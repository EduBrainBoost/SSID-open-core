# ADR-0067: Canonical Agent Pack in 24_meta_orchestration

- Status: ACCEPTED
- Date: 2026-03-05
- Decision: Move Claude agent definitions to `24_meta_orchestration/agents/claude/`

## Context

SSID uses 11 Claude subagents (01-Planner through 11-Board Manager) defined as
markdown files with YAML frontmatter. These were stored only in SSID-EMS
`.claude/agents/` without version control in the SSID repo and without
integrity verification.

ROOT-24-LOCK requires all orchestration artifacts under their canonical root.
Agent definitions are orchestration artifacts.

## Decision

1. Canonical source: `24_meta_orchestration/agents/claude/*.md` (tracked in SSID)
2. SHA256 manifest: `24_meta_orchestration/agents/claude/agents_manifest.json`
3. Sync target: SSID-EMS `.claude/agents/` receives deterministic copy (no symlink)
4. No `.claude/agents/` in SSID git (local only, not tracked)

## Consequences

- Agent definitions are version-controlled and PR-gated
- Integrity verifiable via manifest hashes
- SSID-EMS sync is a deterministic copy operation
- Changes to agents require PR review like any other code change
