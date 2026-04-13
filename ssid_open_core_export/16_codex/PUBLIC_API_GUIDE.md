# SSID-open-core Public API Guide

This document describes the 5 exported roots that form the public API of SSID-open-core.

## Overview

SSID-open-core exports exactly **5 roots** as the public API. These roots are:

| Root | Purpose | Status | Use Case |
|------|---------|--------|----------|
| `03_core` | Runtime & validators | ✅ Exported | Core SSID operations |
| `12_tooling` | CLI tools & scripts | ✅ Exported | Deployment & validation |
| `16_codex` | Architecture & governance | ✅ Exported | Policy & decisions |
| `23_compliance` | Policies & audit | ✅ Exported | Compliance & governance |
| `24_meta_orchestration` | Coordination & registry | ✅ Exported | Multi-agent orchestration |

## Root Details

### 03_core — SSID Runtime

**Purpose:** Core SSID system runtime and validators

**Key Components:**
- Identity primitives and data structures
- Cryptographic validators
- State-of-Truth (SoT) core logic
- Event processing

**Usage:**
```python
from ssid_core.validators import IdentityValidator
from ssid_core.primitives import Subject

validator = IdentityValidator()
subject = Subject.from_did("did:...")
is_valid = validator.validate(subject)
```

**Stability:** Stable for v0.1.x  
**Breaking Changes:** Will follow semantic versioning

---

### 12_tooling — Tools & CLI

**Purpose:** Command-line tools, validation scripts, deployment utilities

**Key Scripts:**
- `validate_public_boundary.py` — Export boundary validation
- `ssid_dispatcher.py` — Task dispatcher
- `sot_validator.py` — Source-of-Truth validation
- Compliance checkers and auditors

**Usage:**
```bash
# Validate export boundary
python 12_tooling/scripts/validate_public_boundary.py

# Run all gates
python 12_tooling/cli/run_all_gates.py

# Check SoT alignment
python 12_tooling/cli/sot_validator.py --verify-all
```

**Stability:** Stable CLI interfaces  
**Deprecation:** 6-month notice for breaking changes

---

### 16_codex — Architecture & Governance

**Purpose:** Architecture decisions, governance policies, standards

**Key Documents:**
- **ADRs** — Architecture Decision Records (decisions/)
- **EXPORT_BOUNDARY.md** — Policy definition
- **GOVERNANCE_MAINTENANCE_PROCEDURES.md** — Operations manual
- **PHASE_*.md** — Implementation roadmaps

**Usage:**
- Reference for understanding architecture
- Source-of-truth for governance policy
- Examples and templates for contributions

**Stability:** Policy changes require RFC  
**Amendment Process:** See GOVERNANCE_MAINTENANCE_PROCEDURES.md

---

### 23_compliance — Compliance Policies

**Purpose:** OPA policies, compliance rules, audit framework

**Key Components:**
- `policies/` — Open Policy Agent rules
- `audit/` — Audit trail and evidence
- `rules/` — Compliance rule definitions

**Usage:**
```bash
# Evaluate compliance policy
opa eval -d 23_compliance/policies/ [input]

# Check audit evidence
python 23_compliance/validators/check_export_compliance.py
```

**Stability:** Policy-compatible with v0.1.x  
**Changes:** Require governance review

---

### 24_meta_orchestration — Coordination

**Purpose:** Multi-agent coordination, task dispatcher, registry

**Key Components:**
- Dispatcher core (non-custodial task routing)
- Agent registry (canonical list of trusted agents)
- Manifest validation (coordination contracts)
- State management

**Usage:**
```python
from meta_orchestration.dispatcher import Dispatcher
from meta_orchestration.registry import AgentRegistry

dispatcher = Dispatcher()
registry = AgentRegistry()

# Dispatch task to agent
result = dispatcher.dispatch(task, agent_id)
```

**Stability:** Stable dispatcher interface  
**Extensions:** Require ADR approval

---

## API Stability Guarantees

### v0.1.0 (Current)

- ✅ All APIs documented and stable
- ✅ No breaking changes expected
- ✅ Minor improvements and bug fixes only
- ✅ Semantic versioning followed

### v0.2.0 (Coming Q2 2026)

- New features and enhancements
- Backward compatible with v0.1.x
- Deprecation warnings for future changes

### v1.0.0 (Coming Q3 2026)

- Possible breaking changes
- Major version bump for incompatibilities
- 6-month deprecation notice for removals

## Contribution Rules

### Only These 5 Roots Accept Contributions

- ✅ `03_core` — Code changes accepted
- ✅ `12_tooling` — New tools/scripts accepted
- ✅ `16_codex` — ADRs and governance docs accepted
- ✅ `23_compliance` — Policy changes require RFC
- ✅ `24_meta_orchestration` — Extensions require ADR

### Other 19 Roots

The remaining 19 roots are **scaffolds**. They do NOT accept contributions in this repository:
- ❌ `01_ai_layer`, `02_audit_logging`, etc. — No contributions
- 🔗 Contribute to **canonical SSID** instead (private repository)

### Amendment Process

To propose changes to governance, export boundary, or policies:

1. **Create RFC** in `16_codex/rfcs/`
2. **Discuss** in GitHub Discussions
3. **Get approval** from governance lead
4. **Create ADR** documenting the decision
5. **Update policy** in EXPORT_BOUNDARY.md
6. **Run validation** gates
7. **Create PR** with evidence

See [GOVERNANCE_MAINTENANCE_PROCEDURES.md](GOVERNANCE_MAINTENANCE_PROCEDURES.md) for details.

## Deprecation Policy

### Timeline

- **Announcement** — Public notice on GitHub
- **Deprecation Period** — 6 months minimum
- **Removal** — Only in major version (v1.0, v2.0, etc.)
- **Documentation** — Migration guide provided

### Example

```
v0.1.0 — New API introduced
v0.2.0 — Old API deprecated (works, but warns)
v1.0.0 — Old API removed
```

## FAQ

### Can I fork and modify SSID-open-core?

Yes! It's open-source under Apache 2.0. Fork, modify, and contribute back via PR.

### Can I use SSID-open-core in production?

Yes, v0.1.0 is production-ready. Ensure you understand the 5-root model and governance requirements.

### What if I need more than the 5 roots?

Those are in canonical SSID (private). You have two options:
1. Use what's available in the 5 exported roots
2. Contribute to canonical SSID (if you have access)

### Can the export boundary change?

Only via RFC + ADR + governance approval. See amendment process above.

### Where's the REST API documentation?

API endpoints are exposed through `12_tooling` and documented via OpenAPI specs in `16_codex/api-specs/`.

See [16_codex/api-specs/](api-specs/) for complete API documentation.

---

## Support & Questions

- 📖 **Documentation:** [README.md](../README.md), [EXPORT_BOUNDARY.md](EXPORT_BOUNDARY.md)
- 💬 **Questions:** [GitHub Discussions](https://github.com/EduBrainBoost/SSID-open-core/discussions)
- 🐛 **Issues:** [GitHub Issues](https://github.com/EduBrainBoost/SSID-open-core/issues)
- 🔒 **Security:** [SECURITY.md](../SECURITY.md)

---

**Version:** v0.1.0  
**Last Updated:** 2026-04-13  
**Status:** Stable, Production-Ready
