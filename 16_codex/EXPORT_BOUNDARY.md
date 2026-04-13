# SSID Open-Core Export Boundary Specification

**Last Updated**: 2026-04-13  
**Status**: AUTHORITATIVE (Phase 2b)  
**Source-of-Truth**: Canonical SSID policy (16_codex/opencore_export_policy.yaml)

---

## Quick Reference

**SSID-open-core is a public derivative of SSID containing 5 root modules (the public API).**

| Exported | Count | Roots |
|----------|-------|-------|
| ✓ Public API | 5 | 03_core, 12_tooling, 16_codex, 23_compliance, 24_meta_orchestration |
| ✗ Denied | 19 | All others (see below) |
| ✓ Repository Structure | 24 | All roots preserved for ROOT-24-LOCK consistency |

---

## Exported Roots (5) — Public API

### 03_core
**Purpose**: SoT validator core, identity primitives  
**Contents**: Smart contracts, identity resolver, core validation logic  
**Public Safety**: ✓ No secrets, no partner deps, no internal-only algorithms  
**Status**: EXPORTED

### 12_tooling
**Purpose**: CLI tools, gates, dispatcher wrapper  
**Contents**: Command-line interfaces, validation scripts, automation tools  
**Public Safety**: ✓ No hardcoded endpoints, no credentials, generic tooling  
**Status**: EXPORTED

### 16_codex
**Purpose**: Architecture decision records, SoT contracts, knowledge base  
**Contents**: ADRs (decisions), governance policies, capability specs  
**Public Safety**: ✓ Documentation-only, no code secrets, governance is open  
**Status**: EXPORTED

### 23_compliance
**Purpose**: OPA policies, compliance rules, exception allowlist  
**Contents**: Policy enforcement rules, audit logs, exception handling  
**Public Safety**: ✓ Policies are generic, allowlist is anonymized  
**Status**: EXPORTED

### 24_meta_orchestration
**Purpose**: Dispatcher core, SoT artifact registry, meta-orchestration  
**Contents**: Dispatcher implementation, artifact registries, coordination logic  
**Public Safety**: ✓ Dispatcher interface is public; no prod credentials  
**Status**: EXPORTED

---

## Denied Roots (19) — NOT Exported

| Root | Reason | IP Risk | NDA Risk | Security Risk | Status |
|------|--------|---------|----------|---------------|--------|
| **01_ai_layer** | AI/ML algorithms, scoring, EU AI Act infrastructure | CRITICAL: Scoring algos | — | DORA compliance logic | DENIED |
| **02_audit_logging** | Hash ledger, evidence chain, WORM storage | — | — | Evidence quarantine chain | DENIED |
| **04_deployment** | CI/CD, infrastructure, Kubernetes, Terraform | — | — | Infra topology, secrets risk | DENIED |
| **05_documentation** | Internal developer guides, partner-specific runbooks | — | HIGH: Partner guides | — | DENIED |
| **06_data_pipeline** | ETL/ELT, event streams, data architecture | MEDIUM: Data flows | HIGH: Partner integrations | — | DENIED |
| **07_governance_legal** | eIDAS, MiCA, DSGVO, DAO rules, legal specifics | — | CRITICAL: Legal clauses | — | DENIED |
| **08_identity_score** | Scoring algorithms, reputation logic | CRITICAL: Proprietary algos | — | — | DENIED |
| **09_meta_identity** | DID schemas, wallet logic, identity lifecycle | MEDIUM: Core logic | HIGH: Partner schemas | — | DENIED |
| **10_interoperability** | DID resolver, cross-chain, protocol adapters | — | CRITICAL: Partner protocols | MEDIUM: Cross-chain security | DENIED |
| **11_test_simulation** | Test infrastructure, chaos engineering, mock chains | — | — | Test harness (public-safe but not core) | DENIED |
| **13_ui_layer** | Frontend, dashboards, admin GUIs | — | — | — | DENIED |
| **14_zero_time_auth** | WebAuthn, zero-time login, biometric auth | — | — | CRITICAL: Auth algorithms | DENIED |
| **15_infra** | Cloud provisioning, secrets/vault, load balancing | — | — | CRITICAL: Secrets, infra details | DENIED |
| **17_observability** | Metrics, tracing, alerting, SIEM configuration | — | — | MEDIUM: Monitoring internals | DENIED |
| **18_data_layer** | Database schemas, GraphDB, encryption-at-rest | — | — | MEDIUM: DB structure | DENIED |
| **19_adapters** | External API adapters, payment providers, partner SDKs | MEDIUM: Adapter internals | CRITICAL: Partner contracts | HIGH: Payment flows | DENIED |
| **20_foundation** | SSID token, tokenomics, DAO treasury | MEDIUM: Token logic | HIGH: Financial mechanics | HIGH: Smart contract | DENIED |
| **21_post_quantum_crypto** | Kyber, Dilithium, quantum-safe migration | — | — | CRITICAL: Crypto implementation | DENIED |
| **22_datasets** | Public datasets, hash references, consent log | — | — | MEDIUM: PII structures | DENIED |

---

## Exception Process

**To add a previously denied root to the export boundary:**

1. **File RFC** in `16_codex/rfcs/RFC_NNNN_export_boundary_exception_<root>.md`
   - Justify why the root should be public-safe
   - Address IP, NDA, and security risks
   - Propose deny_globs for sensitive subpaths

2. **Request Approval**
   - Canonical SSID policy maintainer
   - Security/compliance review
   - Legal review (if NDA risks exist)

3. **Write ADR** (e.g., ADR-0021)
   - Document decision and rationale
   - Link to RFC and approval evidence

4. **Update Policies**
   - Add root to `allow_prefixes` in opencore_export_policy.yaml
   - Remove from deny_roots
   - Add deny_globs for restricted subpaths
   - Update this file

5. **CI Validation**
   - All export gates must PASS
   - validate_public_boundary.py runs over entire root
   - No secrets/PII found

---

## Scaffolded Roots (ALL 24)

To maintain ROOT-24 architectural consistency, all 24 roots exist in the repository:
- **Exported roots** (5): Full content, validated for public safety
- **Denied roots** (19): Empty or minimal scaffolds, not exported, not validated for public content

This structure ensures:
- ✓ Root-24 lock maintained (all 24 roots present)
- ✓ Derivative relationship clear (only 5 are public)
- ✓ Migration path available (roots can be added via exception process)

---

## Validation Pipeline

Every push to SSID-open-core runs:

1. **Structure Guard** — Verify all 24 roots exist; no unauthorized root-level items
2. **Duplicate Guard** — Detect duplicate files across roots
3. **OPA Policy** — Enforce compliance rules via `23_compliance/public_export_policy.rego`
4. **Export Boundary Validator** — Scan 5 exported roots for:
   - No private repo references
   - No absolute local paths
   - No secrets (regex patterns)
   - No .env/.key/.pem files
5. **SoT Validator** — Verify governance documents are consistent
6. **QA Suite** — Hash-based quality checks (no stdout/stderr)

---

## Relationship to Other Governance

| Governance Rule | Implication |
|---|---|
| **ROOT-24-LOCK** | All 24 roots must exist; structure immutable |
| **SAFE-FIX** | Any policy change is audited (SHA256 before/after) |
| **AGENTS.md** | Contributions must respect this boundary |
| **CONTRIBUTING.md** | Only 5 exported roots accept contributions |
| **Canonical SSID Policy** | This document is derived from; SSID is SoT |

---

## FAQ

**Q: Can I add a denied root to open-core?**  
A: Yes, via the exception process (RFC → approval → ADR → policy update).

**Q: Why is 11_test_simulation denied if tests run in CI?**  
A: Export tests moved to 12_tooling (exported root). Test infrastructure itself is not part of public API.

**Q: Can I contribute to a denied root?**  
A: No. Changes belong in canonical SSID. Contributions to denied roots in open-core will be rejected.

**Q: Is this policy permanent?**  
A: No. It can evolve via RFC + governance approval. As of 2026-04-13, it reflects canonical SSID policy (v2.0.0).

**Q: What if SSID policy changes?**  
A: SSID-open-core policy is updated to match (derivative model). Changes are reflected in ADRs + evidence trail.

---

**Document Source**: 16_codex/EXPORT_BOUNDARY.md  
**Last Policy Sync**: 2026-04-13 (ADR-0019 adoption)  
**Next Review**: 2026-07-13 (quarterly)
