# 16_codex — Source of Truth & System Documentation

**Classification:** Governance — Authoritative SoT Repository
**SoT Version:** v4.1.0
**Status:** ROOT-24-LOCK

## Purpose

Central Source of Truth (SoT) repository for the SSID platform. Houses the canonical
system architecture, governance contracts, agent definitions, decision records, phase
documentation, and the authoritative structure specifications (Level 3 MAX definitions).
This is the single authoritative source for all system-wide structural and governance
decisions. Final authority resides with `03_core`.

This module does NOT:
- Store runtime data or customer PII
- Contain executable business logic (specifications only)
- Hold secrets or credentials

## Not Maintained Here

| Domain | Central Location |
|--------|-----------------|
| Compliance execution | `23_compliance/` |
| Runtime evidence | `02_audit_logging/` |
| Global registry | `24_meta_orchestration/registry/` |

## Structure

| Directory       | Purpose                                            |
|-----------------|----------------------------------------------------|
| `docs/`         | Module-level documentation                          |
| `architecture/` | System architecture specifications                  |
| `agents/`       | Agent definitions and prompt contracts              |
| `contracts/`    | Governance and interface contracts                  |
| `decisions/`    | Architecture Decision Records (ADRs)                |
| `governance/`   | Governance rules and enforcement policies           |
| `phases/`       | Phase documentation (Phase 0-8+)                    |
| `archives/`     | Archived specifications and superseded documents    |
| `local_stack/`  | Local development stack specifications              |
| `config/`       | Codex configuration                                 |
| `shards/`       | 16 domain shards                                    |

## Key Files

- `SSID_structure_level3_part1_MAX.md` — Level 3 structure (Part 1)
- `SSID_structure_level3_part2_MAX.md` — Level 3 structure (Part 2)
- `SSID_structure_level3_part3_MAX.md` — Level 3 structure (Part 3)
- `SSID_structure_gebuehren_abo_modelle.md` — Fee and subscription model structure
- `opencore_export_policy.yaml` — Open-core export boundary policy

## Governance

All changes to codex specifications require the RFC process. No direct modifications
without documented approval chain.

## Interfaces

| Direction | Central Path | Description |
|-----------|-------------|-------------|
| Output | `17_observability/logs/codex/` | Log output specification |
| Output | `23_compliance/evidence/codex/` | Evidence path (hash-only) |
