# SSID Open Core

Public derivative of the SSID Self-Sovereign Identity Platform.
Contains the open-source subset: core validators, tooling, codex, compliance policies, and meta-orchestration.

## Open-Core Scope

This repository exposes **5 root modules** from the canonical SSID architecture:

| Root | Purpose |
|------|---------|
| `03_core` | SoT validator core, identity primitives |
| `12_tooling` | CLI tools (gates, dispatcher, validator), guard scripts |
| `16_codex` | Architecture Decision Records (ADRs), SoT contracts |
| `23_compliance` | OPA policies, root-level exception allowlist |
| `24_meta_orchestration` | Canonical dispatcher, SoT artifact registry |

All other SSID roots are maintained in the private canonical repository and are not part of this open-core distribution.

## Prerequisites

- Python 3.11+
- `pip install pyyaml`
- OPA CLI (optional, for policy gate)

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

- No secrets, keys, or PII in the repository.
- `.claude/` is a local-only dev config directory (gitignored, see [ADR-0005](16_codex/decisions/ADR_0005_claude_local_dev_root_exception.md)).
- Hash-only evidence: no agent stdout/stderr or prompts persisted.
- Report vulnerabilities via GitHub Security Advisories.

## License

Apache-2.0. See [LICENSE](LICENSE).
