# ADR-0069: Agent Pack Verifier and Deterministic Manifest

**Status:** Accepted
**Date:** 2026-03-05
**TaskSpec:** TS027_AGENT_PACK_SYNC

## Context

ADR-0067 established `24_meta_orchestration/agents/claude/` as the canonical location for Claude Code agent definitions. The initial manifest used a non-deterministic format with timestamps, making reproducibility verification impossible.

## Decision

1. **Deterministic manifest format** — `agents_manifest.json` contains `version` and `agents` array only. No timestamps, no metadata. Sorted lexicographically by filename.
2. **Stdlib-only verifier** — `12_tooling/cli/agents_pack.py` provides `verify` (check SHA256 hashes) and `emit-manifest` (regenerate manifest). No external dependencies.
3. **Registry entry** — `24_meta_orchestration/registry/agents_registry.json` records canonical path, manifest name, and sync targets.
4. **Tests skip on stripped tree** — `test_agents_pack.py` uses `pytest.mark.skipif` when canonical dir is absent.

## Consequences

- Manifest is byte-reproducible across runs.
- Drift detection via `agents_pack.py verify` can run in CI and locally.
- SSID-EMS sync tool (PR B) can verify copies against SSID manifest.
