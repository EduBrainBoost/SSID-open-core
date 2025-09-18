# SSID Structure Policy v1.0

## Purpose

This policy defines the core structural requirements for the SSID OpenCore repository according to Blueprint 4.x standards. It enforces the 24-module architecture, common file requirements, and centralization principles.

## Policy Overview

### Core Requirements

- **24 Fixed Root Modules**: Exactly 24 modules numbered 01-24 with specific naming convention
- **Common MUST Files**: Each module requires `module.yaml`, `README.md`
- **Common MUST Directories**: Each module requires `docs/`, `src/`, `tests/`
- **Centralization**: Policies, registry, evidence centralized to prevent duplication
- **Forbidden Local Directories**: No local `registry/`, `policies/`, `risk/`, `evidence/`, etc.

### Compliance Threshold

- **95% compliance required** for structure validation to pass
- Missing critical files result in -5 points each
- Forbidden directories result in validation failure

## File Structure

```
structure_policy_v1_0/
├── module.yaml              # Policy module metadata
├── README.md                # This documentation
└── structure_policy_v1_0.yaml  # Policy implementation
```

## Implementation

### Validation Scripts
- **Primary**: `12_tooling/scripts/structure_guard.sh`
- **Tests**: `23_compliance/tests/unit/test_structure_policy_vs_md.py`
- **CI Gates**: `24_meta_orchestration/triggers/ci/gates/structure_lock_l3.py`

### Enforcement Points
1. **Pre-commit hook**: `12_tooling/hooks/pre_commit/structure_validation.sh`
2. **CI/CD pipeline**: GitHub Actions + structure lock gates
3. **Manual validation**: Structure guard script

## Policy Details

### Root Module Requirements

All 24 modules must exist with exact naming:
- `01_ai_layer` through `24_meta_orchestration`
- Each module must contain the common MUST files and directories

### Centralized Locations

| Function | Central Path | Purpose |
|----------|--------------|---------|
| Registry | `24_meta_orchestration/registry/` | Module management |
| Policies | `23_compliance/policies/` | Policy centralization |
| Evidence | `23_compliance/evidence/` | Audit evidence |
| Exceptions | `23_compliance/exceptions/` | Structure exceptions |
| Risk | `07_governance_legal/risk/` | Risk register |

### Exceptions

The following are explicitly allowed:
- `.git*` directories and files
- Standard repository files (`LICENSE`, `README.md`, etc.)
- Development tool configurations (`.venv`, `.continue`, etc.)

## Version History

### v1.0 (2025-09-18)
- **Migration**: Moved from non-versioned `structure_policy.yaml`
- **Blueprint**: Updated to Blueprint 4.x requirements
- **Versioning**: Implemented proper policy versioning structure
- **Dependencies**: Added explicit dependency tracking
- **Enforcement**: Enhanced CI/CD integration

## Maintenance

- **Owner**: Community Lead (compliance@ssid.org)
- **Backup**: Technical Lead (tech@ssid.org)
- **Review Frequency**: Quarterly
- **Next Review**: 2025-12-18

## References

- Blueprint 4.x Specification: `24_meta_orchestration/locks/SSID_opencore_structure_level3.md`
- Policy Versioning Standard: Blueprint 4.x Section "Versioned Regulatory References"
- Anti-Gaming Controls: `23_compliance/anti_gaming/`

---

**Legal & Audit Disclaimer:**
The SSID-open-core repository meets the Blueprint 4.x maximal standard according to local build and test systems.
All compliance, badge, and audit reports apply solely to the local repository and build state.
**This does NOT constitute official certification under MiCA, eIDAS, DORA, ISO, SOC2, or any similar regulations.**
External authorities, auditors, and reviewers are EXPLICITLY invited to review all artifacts free of charge and independently.
Official certifications require an external audit in accordance with the applicable regulatory requirements.