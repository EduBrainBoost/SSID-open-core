# Source of Truth (SoT) Enterprise Policy

## Purpose

This document defines the canonical Source of Truth hierarchy for the SSID system.
All structural, policy, and configuration decisions must trace back to these authoritative sources.

## SoT Hierarchy

### Level 0: Master Definition
- **File**: `16_codex/ssid_master_definition_corrected_v1.1.1.md`
- **Scope**: Defines the 24 canonical root modules, their purpose, and boundaries
- **Authority**: Highest — all other artifacts must align with this definition

### Level 1: Structure Level 3 Definitions
- **Files**: `16_codex/SSID_structure_level3_part1_MAX.md`, `part2`, `part3`
- **Scope**: Detailed sub-module structure within each root
- **Authority**: Defines expected directory layout per root module

### Level 2: Structure Policy
- **File**: `23_compliance/policies/structure_policy.yaml`
- **Scope**: Machine-readable enforcement of ROOT-24-LOCK
- **Authority**: CI gates and validators consume this directly

### Level 3: Exceptions Registry
- **Files**:
  - `23_compliance/exceptions/root_level_exceptions.yaml`
  - `23_compliance/exceptions/structure_exceptions.yaml`
- **Scope**: Documented deviations from strict policy
- **Authority**: Every exception requires justification and approval

## Conflict Resolution

When sources conflict, higher levels take precedence:
1. Master Definition (Level 0) overrides all
2. Level 3 Definitions override policy files
3. Policy files override exception files
4. Exception files are the lowest authority

## Prohibited Patterns

- Inventing structure not defined in the SoT hierarchy
- Claiming a file is "canonical" without tracing to a Level 0/1 source
- Modifying policy files without corresponding SoT update
- Creating parallel SoT documents outside `16_codex/`

## Review Cadence

- Master Definition: reviewed quarterly or on architectural changes
- Structure policies: reviewed on every PR that modifies root structure
- Exceptions: reviewed monthly, expired exceptions auto-revoked
