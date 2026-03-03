# ADR 0005: .claude Local Developer Config Root Exception

## Status
Accepted

## Date
2026-02-12

## Context
Claude Code (Anthropic CLI tool) creates a `.claude/` configuration directory at the project root.
This directory is tool-managed and cannot be relocated to a non-root path.
Under ROOT-24-LOCK, every new root-level exception is governance-relevant because it increases the attack surface and can affect deterministic builds/CI.

## Decision
1. Allow `.claude/` as a root-level exception in `23_compliance/exceptions/root_level_exceptions.yaml`.
2. `.claude/` MUST be listed in `.gitignore` and MUST NOT be tracked by git.
3. `.claude/` MUST NOT contain secrets, credentials, or build-affecting artifacts.
4. `.claude/` is classified as a local-only developer configuration directory (same category as `.pytest_cache/`).
5. CI environments will not have `.claude/` present; the exception is defensive only.

## Constraints
- `.claude/` contents are ephemeral and developer-local.
- The structure guard treats it as an allowed directory, not a numbered module.
- No SoT artifacts, contracts, or shards may reside inside `.claude/`.

## Evidence
- `git ls-files -- .claude` returns empty (not tracked).
- `git check-ignore -v .claude/` matches `.gitignore:1:.claude/`.
- `root_level_exceptions.yaml` diff contains only the `.claude` addition.

## Consequences
1. Root layout remains strict; `.claude/` is the only new exception since ROOT-24-LOCK.
2. Developers using Claude Code can work without structure guard failures.
3. CI remains unaffected (`.claude/` is not present in clean checkouts).
4. No feature behavior is added; this is a tooling-compatibility exception.
