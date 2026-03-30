> DEPRECATED: Historical reference only.
> Canonical entrypoint: `python 12_tooling/cli/ssid_dispatcher.py ...`
> Canonical dispatcher (internal): `24_meta_orchestration/dispatcher/e2e_dispatcher.py`

# SOT Rules Overview

This document provides a comprehensive reference of all Source of Truth (SoT) rules enforced in the SSID Agent Stack.

## Rule Priority (MOSCOW)

### MUST (Critical - Hard Fail)

| ID | Rule | Description | Severity |
|----|------|-------------|----------|
| SOT_AGENT_001 | Dispatcher Entry Point | `12_tooling/cli/ssid_dispatcher.py` must exist as single entry point | critical |
| SOT_AGENT_002 | Agent Governance Docs | AGENTS.md, WORKFLOW.md, FAILURES.md must exist | critical |
| SOT_AGENT_003 | Data Minimization | Evidence must be hash-only (MINIMAL mode) | critical |
| SOT_AGENT_004 | Canonical Artifacts | All 6 SoT artifacts must be present | high |
| SOT_AGENT_005 | No Duplicates | No duplicate rule_ids, functions, or CLI flags | critical |
| SOT_AGENT_006 | Root-24-LOCK | Write-Gate must enforce allowed_paths | critical |

### SHOULD (High - Soft Fail)

| ID | Rule | Description |
|----|------|-------------|
| SOT_GATE_001 | Patch Strategy | Changes must follow single-commit or no-rewrites |
| SOT_GATE_002 | Evidence Bundle | All runs must produce evidence |
| SOT_GATE_003 | Gate Chain | All 4 gates must pass |

### COULD (Medium - Warning)

| ID | Rule | Description |
|----|------|-------------|
| SOT_OPT_001 | Documentation | New modules should have docs |
| SOT_OPT_002 | Tests | New features should have tests |

### WON'T (Explicitly Excluded)

| ID | Rule | Description |
|----|------|-------------|
| SOT_EXCL_001 | Prompt Storage | No AI prompts in evidence |
| SOT_EXCL_002 | Scoring | No numerical compliance scores |

## Canonical SoT Artifacts

1. `03_core/validators/sot/sot_validator_core.py` - Core validation logic
2. `23_compliance/policies/sot/sot_policy.rego` - OPA policies
3. `16_codex/contracts/sot/sot_contract.yaml` - Rule definitions
4. `12_tooling/cli/sot_validator.py` - CLI validator
5. `11_test_simulation/tests_compliance/test_sot_validator.py` - Tests
6. `02_audit_logging/reports/SOT_MOSCOW_ENFORCEMENT_V3.2.0.md` - Enforcement doc

## Validation Commands

```bash
# Run all SoT checks
python3 12_tooling/cli/sot_validator.py --verify-all

# Run gate chain
python3 12_tooling/cli/run_all_gates.py

# Run pytest
python3 -m pytest 11_test_simulation/tests_compliance/
```

## Related Documentation

- [AGENTS.md](16_codex/agents/AGENTS.md) - Agent roles and governance
- [WORKFLOW.md](16_codex/agents/WORKFLOW.md) - Operational workflow
- [FAILURES.md](16_codex/agents/FAILURES.md) - Failure log
- [SOT_MOSCOW_ENFORCEMENT_V3.2.0.md](02_audit_logging/reports/SOT_MOSCOW_ENFORCEMENT_V3.2.0.md) - Full enforcement rules
