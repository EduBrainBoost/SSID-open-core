# SSID-open-core

**SSID-open-core** is a sanitized, public-facing open-core mirror of the private SSID product core. It provides public SDKs, schemas, adapter interfaces, and reference implementations — nothing more.

## What It Is

- A **one-way generated mirror** from the private SSID repository
- Contains only **public-safe** content: schemas, interfaces, examples, documentation
- Serves as the **public entry point** for external developers integrating with SSID
- Maintains full **provenance**, **license compliance**, and **private-content isolation**

## What It Is NOT

- ❌ **Not** the SSID source of truth (SoT)
- ❌ **Not** a development repository for private SSID code
- ❌ **Not** a reverse-sync target — content flows SSID → OpenCore only
- ❌ **Not** a container for private Level-3 implementation details
- ❌ **Not** a host for secrets, PII, credentials, or internal tooling

## Architecture

```
PRIVATE SSID SoT
       |
       v
bounded export manifest
       |
       v
sanitization / provenance / license / secret / PII gates
       |
       v
SSID-open-core worktree
       |
       v
24 public root modules
       |
       v
PR + CI + verifier + release evidence
       |
       v
PUBLIC RELEASE (only after explicit release gate)
```

## 24-Root Public Structure

| Root | Public Scope |
|------|-------------|
| `01_ai_layer` | Public AI interfaces, evaluation examples, provider-neutral stubs |
| `02_audit_logging` | Public evidence schemas, verification formats, retention concepts |
| `03_core` | Approved public protocol/core APIs, public domain schemas |
| `04_deployment` | Infrastructure-agnostic examples, sanitized developer templates |
| `05_documentation` | OpenCore architecture, public SDK/API docs, ADRs |
| `06_data_pipeline` | Synthetic/open-data pipeline examples, public schemas |
| `07_governance_legal` | Public LICENSE/SECURITY/contribution/governance notices |
| `08_identity_score` | Public scoring interfaces, synthetic fixtures |
| `09_meta_identity` | Public DID/VC/meta-identity schemas, resolver interfaces |
| `10_interoperability` | Public standards mappings, adapter contracts, example connectors |
| `11_test_simulation` | Unit/integration/conformance/policy tests for public artifacts |
| `12_tooling` | Public validators, generators, release helpers |
| `13_ui_layer` | Public demos, SDK playground, sample components |
| `14_zero_time_auth` | Concept docs, mocks, protocol examples, public auth interfaces |
| `15_infra` | Sanitized local/developer examples, public infrastructure blueprints |
| `16_codex` | Public playbooks, patterns, guides for external developers |
| `17_observability` | Public score/evidence summaries, non-sensitive dashboards |
| `18_data_layer` | Public schemas, migration examples, mock repositories |
| `19_adapters` | Public reference adapters for identity, messaging, payments with mocks |
| `20_foundation` | Public utilities, serialization, config helpers |
| `21_post_quantum_crypto` | Public crypto-agility interfaces, benchmarks, examples |
| `22_datasets` | Synthetic/open/reference datasets with source/license metadata |
| `23_compliance` | Public policies, release evidence, exception schema, reviews |
| `24_meta_orchestration` | Public registries, export/release manifests, pipeline descriptions |

## Local Development

```bash
# Clone
git clone https://github.com/EduBrainBoost/SSID-open-core.git
cd SSID-open-core

# Install
pip install -e "src[opencore]"

# Run tests
python -m pytest tests/ -v

# Verify 24-root structure
python -c "from src.opencore import OpenCoreCore; c = OpenCoreCore(); print(c.validate_root_24())"
```

## Security

- All content is public-safe by design
- No secrets, PII, credentials, or private paths
- Automated secret scanning, PII scanning, license scanning in CI
- Private leakage detection enforced via policy tests

## Contribution

Contributions to public content are welcome via PR. All contributions are reviewed for:
- License compatibility
- No private SSID content leakage
- Policy compliance
- Test coverage

See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## License

MIT License — see [LICENSE](LICENSE) for details.

## Release Verification

To verify a release:
1. Check the [release manifest](24_meta_orchestration/registry/release_manifest.json)
2. Verify SHA256 checksums against [SHA256SUMS](SHA256SUMS)
3. Confirm CI workflow runs are green
4. Review [evidence](23_compliance/evidence/) for the build

## Compliance Disclaimer

This repository contains **public technical interfaces only**. It does not constitute:
- Legal or regulatory compliance certification
- Investment or financial advice
- Security guarantees for production systems
- A replacement for the private SSID product

Public badges reflect **static specification verification**, not runtime certification.

---

**Repository Role:** Sanitized Public Mirror  
**One-Way Export:** SSID → OpenCore (never reverse)  
**Release Policy:** GATED — public publication requires explicit owner approval
