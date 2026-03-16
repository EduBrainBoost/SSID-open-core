# AGENTS

Scope: entire `SSID-open-core` repository.

Read first when relevant:
- `README.md`
- `CONTRIBUTING.md`
- `16_codex/README.md`
- `16_codex/decisions/`

Purpose:
- Maintain the open/public derivative of SSID content without leaking private repo internals.

Hard rules:
- Keep this repository public-safe.
- Do not import private operational data, audit evidence, secrets, or internal-only paths from `SSID` or `SSID-EMS`.
- Preserve existing structure and governance decisions in `16_codex/decisions/`.
- Prefer deterministic, reviewable deltas over broad rewrites.

Working model:
- Treat this repo as a curated export/open-core surface, not as a dump of private source material.
- Keep changes aligned with existing ADRs and module layout.
- If content appears to require private SSID context, stop and surface that dependency explicitly instead of guessing.

When editing:
- Stay within requested scope and existing module boundaries.
- Prefer documentation, governance, and tooling changes that are clearly publishable.
- Note any divergence risk between `SSID` and `SSID-open-core` in the final summary.

Avoid:
- Introducing private-repo references as normative dependencies
- Creating duplicate governance artifacts with conflicting meaning
- Casual structural changes at the repo root
