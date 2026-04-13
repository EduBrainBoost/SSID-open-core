# ADR-0023: Root08 identity_score SoT Enforcement

**Status:** Accepted
**Date:** 2026-02-28T16:30:00Z
**Deciders:** Agent-A (Implementer-Harden), Human Reviewer

## Context

Root08 (`08_identity_score`) baseline scaffold was merged in PR #40 (Root08 A1).
The mandatory files and directories need SoT enforcement to prevent accidental
deletion or structural drift. This follows the established pattern from Root01–07.

## Decision

Add SOT_AGENT_029..036 to the SoT-5 artifact chain:

| Rule | Target | Check |
|------|--------|-------|
| SOT_AGENT_029 | `08_identity_score/module.yaml` | Existence + YAML parseable + required keys (module_id, name, version, status) |
| SOT_AGENT_030 | `08_identity_score/README.md` | Existence + required section headers (Overview, Structure, Interfaces, Policies, Governance, Testing) |
| SOT_AGENT_031 | `08_identity_score/docs/` | Directory existence |
| SOT_AGENT_032 | `08_identity_score/src/` | Directory existence |
| SOT_AGENT_033 | `08_identity_score/tests/` | Directory existence |
| SOT_AGENT_034 | `08_identity_score/models/` | Directory existence |
| SOT_AGENT_035 | `08_identity_score/rules/` | Directory existence |
| SOT_AGENT_036 | `08_identity_score/api/` | Directory existence |

Changes are append-only across all 4 modified SoT artifacts:
- `03_core/validators/sot/sot_validator_core.py`
- `16_codex/contracts/sot/sot_contract.yaml`
- `23_compliance/policies/sot/sot_policy.rego`
- `11_test_simulation/tests_compliance/test_sot_validator.py`

CLI (`12_tooling/cli/sot_validator.py`) unchanged — picks up new rules automatically.

## Consequences

- SoT coverage extended from SOT_AGENT_001..028 to SOT_AGENT_001..036.
- 18 new deterministic tests (PASS + FAIL per rule).
- PR-only workflow maintained; no direct writes.
- No SoT-core behavioral changes — strictly additive enforcement.
