# SSID Open Core

[![CI](https://github.com/EduBrainBoost/SSID-open-core/actions/workflows/open_core_ci.yml/badge.svg)](https://github.com/EduBrainBoost/SSID-open-core/actions/workflows/open_core_ci.yml)
[![CodeQL](https://github.com/EduBrainBoost/SSID-open-core/actions/workflows/codeql.yml/badge.svg)](https://github.com/EduBrainBoost/SSID-open-core/actions/workflows/codeql.yml)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/EduBrainBoost/SSID-open-core/badge)](https://scorecard.dev/viewer/?uri=github.com/EduBrainBoost/SSID-open-core)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Secret Scan](https://github.com/EduBrainBoost/SSID-open-core/actions/workflows/secret-scan.yml/badge.svg)](https://github.com/EduBrainBoost/SSID-open-core/actions/workflows/secret-scan.yml)

Public derivative of the SSID Self-Sovereign Identity Platform.
Contains the open-source subset: core validators, tooling, codex, compliance policies, and meta-orchestration.

## Open-Core Scope

### Exported Roots (Public API)

This repository exposes **5 exported root modules** that form the public API of SSID Open-Core:

| Root | Purpose | Status |
|------|---------|--------|
| `03_core` | SoT validator core, identity primitives | ✓ Exported |
| `12_tooling` | CLI tools (gates, dispatcher, validator), guard scripts | ✓ Exported |
| `16_codex` | Architecture Decision Records (ADRs), SoT contracts | ✓ Exported |
| `23_compliance` | OPA policies, root-level exception allowlist | ✓ Exported |
| `24_meta_orchestration` | Canonical dispatcher, SoT artifact registry | ✓ Exported |

### Scaffolded Roots (Not Exported)

The repository structure includes 19 additional scaffolded root directories (01_ai_layer, 02_audit_logging, 04_deployment, etc.) that represent the full canonical SSID architecture. These are preserved for structural consistency but contain no public content and are not exported.

### Repository Status

- **Exported:** 5 root modules available for public use
- **Scaffolded:** 19 root module directories (structure only, no public content)
- **Total:** 24 roots (ROOT-24 architecture immutable)
- **Distribution:** Open-core subset only; full implementation in private canonical repository

## Prerequisites

- Python 3.11+
- `pip install pyyaml`
- OPA CLI (optional, for policy gate)

## Public Export Validation

The repository includes a deterministic public export pipeline that validates all exported roots for public safety:

```bash
# Build public export manifest and validate boundaries
python 12_tooling/scripts/build_public_export.py

# Validate public boundary (no private refs, secrets, local paths, false mainnet claims)
python 12_tooling/scripts/validate_public_boundary.py

# Generate export status report
python 12_tooling/scripts/generate_export_status_report.py

# Run comprehensive export pipeline tests (27 tests)
python -m pytest 11_test_simulation/tests_export/test_export_pipeline.py -v
```

All exported roots pass public-safety boundary validation:
- ✓ No private repository references
- ✓ No absolute local paths
- ✓ No secrets, keys, or credentials
- ✓ No unbacked mainnet/production claims

## Quickstart

```bash
# Verify repository structure
python 12_tooling/scripts/structure_guard.py

# Run full gate chain (Structure Guard -> SoT -> QA)
python 12_tooling/cli/run_all_gates.py

# Validate all SoT rules
python 12_tooling/cli/sot_validator.py --verify-all

# Check SoT artifact drift
python 12_tooling/cli/sot_diff_alert.py
```

## Core Commands

| Command | Purpose |
|---------|---------|
| `python 12_tooling/scripts/structure_guard.py` | Enforce open-core root layout |
| `python 12_tooling/cli/run_all_gates.py` | Full gate chain (local == CI) |
| `python 12_tooling/cli/sot_validator.py --verify-all` | Validate all SoT rules |
| `python 12_tooling/cli/sot_diff_alert.py` | Detect SoT artifact drift |
| `python 12_tooling/cli/ssid_dispatcher.py` | Dispatcher entry (wraps canonical) |
| `bash 12_tooling/scripts/run_all_gates.sh` | Shell wrapper (CI entry point) |

## Repository Layout

| Path | Role |
|------|------|
| `03_core/validators/sot/` | SoT validator core |
| `12_tooling/cli/` | CLI tools (gates, dispatcher, validator) |
| `12_tooling/scripts/` | Guard scripts (structure, gates) |
| `16_codex/decisions/` | Architecture Decision Records (ADRs) |
| `16_codex/contracts/sot/` | SoT contracts |
| `23_compliance/policies/sot/` | OPA policies |
| `23_compliance/exceptions/` | Root-level exception allowlist |
| `24_meta_orchestration/dispatcher/` | Canonical dispatcher implementation |
| `24_meta_orchestration/registry/` | SoT artifact registry |

## Governance

Changes are accepted exclusively through deterministic gates and review.
Automated workers may propose patches but have no write autonomy without review.

Details: [`16_codex/decisions/`](16_codex/decisions/) (ADRs) | [`CONTRIBUTING.md`](CONTRIBUTING.md)

## Security

- **Public Boundary:** Automated validation on every CI run ensures:
  - No secrets, keys, credentials, or PII in exported roots
  - No absolute local paths (C:\Users, /home/*, /mnt/*)
  - No private repository references (SSID-private, local.ssid, etc.)
  - No false mainnet/production claims without context
  
- **Repository Integrity:**
  - Hash-only evidence chain (no agent stdout/stderr or prompts persisted)
  - `.claude/` is a local-only dev config directory (gitignored, see [ADR-0005](16_codex/decisions/ADR_0005_claude_local_dev_root_exception.md))
  - Structure guard enforces ROOT-24 immutability
  
- **Vulnerability Reporting:** Report security issues via [GitHub Security Advisories](https://github.com/EduBrainBoost/SSID-open-core/security/advisories)

## License

Apache-2.0. See [LICENSE](LICENSE).
