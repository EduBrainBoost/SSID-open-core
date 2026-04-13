# ADR 0001: ROOT-24-LOCK and Change-Control

## Status
Accepted

## Context
- Root-24-LOCK requires deterministic structure and controlled process evolution.
- Governance, process, and structure changes need explicit audit evidence.

## Decision
- Any structure, governance, or process change requires an ADR file in `16_codex/decisions/`.
- Changes without ADR are blocked by repository guard in gate execution.
- Sensitive operational details are redacted when ADR content is public-facing.

## Consequences
- Prevents silent drift in root structure and operating model.
- Keeps change intent auditable and reviewable.
