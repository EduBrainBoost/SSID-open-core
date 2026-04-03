# ADR Process — Architecture Decision Record Governance

**Document Type:** Process & Governance
**Version:** 1.0.0
**Status:** ACTIVE
**Last Updated:** 2026-04-01
**Authority:** 16_codex — Canonical SoT

---

## 1. Overview

Architecture Decision Records (ADRs) are the canonical mechanism for documenting SSID system decisions, governance changes, and RFC-mandated specifications.

**Key Principles:**
- Decisions are **immutable** once accepted
- All root-level changes require an ADR
- ADRs are numbered sequentially (ADR-0001, ADR-0002, ...)
- Status transitions are: `proposed` → `approved` → `accepted` → `superseded` (optional)

---

## 2. Governance Authority

| Role | Authority | Scope |
|------|-----------|-------|
| **Submitter** | Any agent / team member | Propose ADR |
| **Domain Lead** | Domain expert (SSID architect + governance lead) | Review + approve change |
| **Integration Gate** | CI + manual verification | Verify ROOT-24-LOCK compliance |
| **Archive Steward** | 16_codex governance team | Finalize + close |

---

## 3. ADR Lifecycle

### 3.1 Proposal Phase

1. **Create ADR file**
   - Location: `16_codex/decisions/ADR_<NNNN>_<slug>.md`
   - Filename format: ADR number + 4-digit zero-padded sequence + underscore-separated slug
   - Example: `ADR_0083_dispatcher_core_implementation_audit_remediation.md`

2. **Minimum template structure**
   ```markdown
   # ADR-<NNNN>: <Title>

   - **Status:** proposed
   - **Date:** <YYYY-MM-DD>
   - **Scope:** <affected_root>/<component>
   - **RFC:** ADR-ID or None

   ## Context
   Why is this decision needed?

   ## Decision
   What is the decision?

   ## Consequences
   Positive and negative impacts.

   ## Implementation Notes
   Timing, dependencies, assumptions.
   ```

3. **Assign ADR to domain**
   - Notify domain lead via comment or PR annotation
   - Add to relevant root's governance tracking (if applicable)

### 3.2 Approval Phase

1. **Domain lead review**
   - Verify scope alignment with root responsibilities
   - Check for ROOT-24-LOCK violations
   - Request changes if needed (status remains `proposed`)

2. **Approval decision**
   - Update status to `approved` (change is not yet committed)
   - Domain lead adds approval signature / date

3. **Integration gate verification**
   - `.github/workflows/adr_gate.yml` verifies:
     - ADR syntax is valid
     - Referenced roots are within ROOT-24-LOCK
     - No circular dependencies on other ADRs
     - File naming is correct

### 3.3 Acceptance Phase

1. **Implementation begins** (only after approval)
   - Changes are applied to affected roots
   - SAFE-FIX evidence logged for each write operation
   - Tests green

2. **Finalization**
   - Update ADR status to `accepted`
   - Add final date and implementation notes
   - Commit ADR + artifacts in single PR

3. **Archive + Reference**
   - ADR is immutable; future decisions that supersede it create new ADRs
   - Old ADR status becomes `superseded` with reference to new ADR

### 3.4 Supersession (Optional)

When an ADR is no longer active:

```markdown
# ADR-<OLD>: Old Title

- **Status:** superseded
- **Superseded By:** ADR-<NEW>
- **Date Superseded:** <YYYY-MM-DD>
```

---

## 4. ADR Numbering & Sequencing

**Sequence rule:** ADRs are numbered 0001, 0002, ..., 9999 in the order they are created (not by root or domain).

**Current sequence:** ADR-0083 (as of 2026-04-01)

**Next ADR:** ADR-0084

---

## 5. Scope & Change Types

### 5.1 When an ADR is Required

| Type | Examples | Required? |
|------|----------|-----------|
| Root-level restructuring | Moving files between roots | YES |
| New root creation | Adding 25_example_root | YES (RFC required first) |
| Governance policy change | Token distribution, fee model | YES |
| Algorithm changes | Scoring, protocol | YES |
| Major dependency upgrade | Framework version → +major | YES |
| Security hardening | Auth changes, SAFE-FIX exceptions | YES |
| CI/CD workflow changes | New automation, gate modifications | YES |

### 5.2 When an ADR is Optional

| Type | Examples |
|------|----------|
| Documentation updates | README, inline comments |
| Test additions | New test cases, test data |
| Minor bug fixes | Typo fixes, small logic corrections |
| Config tuning | Threshold adjustments (non-policy) |
| Dependency patch versions | v1.0.0 → v1.0.1 |

---

## 6. Implementation Checklist

Before opening ADR for approval:

- [ ] ADR file location: `16_codex/decisions/ADR_<NNNN>_<slug>.md`
- [ ] Status field: `proposed`
- [ ] Context section explains the problem
- [ ] Decision section is clear and actionable
- [ ] Consequences section lists positive + negative impacts
- [ ] Scope field identifies affected roots (must be within ROOT-24-LOCK)
- [ ] No circular dependencies on other ADRs
- [ ] Implementation notes describe timeline + dependencies
- [ ] File naming follows pattern: ADR_<NNNN>_<slug_case>

---

## 7. Governance Contacts

| Domain | Lead | Contact |
|--------|------|---------|
| **Core & Protocol** | SSID Architect | 16_codex governance lead |
| **Token & Finance** | Tokenomics Lead | ADR-0082 authority |
| **Compliance & Legal** | Compliance Lead | 23_compliance governance |
| **Security & Crypto** | Security Lead | 21_post_quantum_crypto authority |

---

## 8. ADR Templates by Domain

### Template A — Core Structural Change

```markdown
# ADR-<NNNN>: <Title>

- **Status:** proposed
- **Date:** <YYYY-MM-DD>
- **Scope:** `03_core/<module>`
- **RFC:** ADR-<ref> or None

## Context
What architectural problem does this solve?

## Decision
What is the chosen solution?

## Consequences
- **Positive:** 
  - Item A
  - Item B
- **Negative:**
  - Item C
- **Neutral:**
  - Item D

## Implementation Notes
- Timeline: <weeks>
- Dependencies: <other ADRs>
- Blockers: <known issues>
```

### Template B — Governance/Policy Change

```markdown
# ADR-<NNNN>: <Policy Name>

- **Status:** proposed
- **Date:** <YYYY-MM-DD>
- **Scope:** `<affected_root>` or global
- **Authority:** 16_codex governance

## Context
What governance or policy issue requires a decision?

## Decision
New policy statement and rules.

## Compliance
- Frameworks affected: <GDPR, SOC2, etc.>
- Evidence path: `23_compliance/<framework>`
- Test/verification method: <method>

## Consequences
Impact on other roots, agents, processes.
```

---

## 9. Integration with SSID Workflow

ADRs are referenced in:
- **Run Gates:** `.github/workflows/adr_gate.yml` (NEW)
- **Agent Tasks:** ADR acceptance is prerequisite for implementation
- **Commit Messages:** Include ADR reference: `fix(core): <description> — ADR-0083`
- **Evidence Logs:** SAFE-FIX logs reference ADR for authority

---

## 10. Change Log

| Version | Date | Notes |
|---------|------|-------|
| 1.0.0 | 2026-04-01 | Initial ADR process documentation; published as G068 remediation |

---

**Document Authority:** 16_codex / SSID Architect
**Next Review:** 2026-07-01 (quarterly)
