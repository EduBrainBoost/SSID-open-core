# Canonical Agent Definitions (Claude)

This directory contains the canonical set of Claude Code agent definitions for the SSID project.

- **11 agents** covering the full SSID workflow (plan, scope, patch, gate, security, evidence, PR, ops, content, design, board).
- **`agents_manifest.json`** — deterministic manifest with SHA256 hashes for each agent file.
- Verification: `python 12_tooling/cli/agents_pack.py verify`
- Manifest regeneration: `python 12_tooling/cli/agents_pack.py emit-manifest`

Runtime sync to `SSID-EMS/.claude/agents/` is handled by `SSID-EMS/ops/agents_sync/sync_agents_from_ssid.py`.
