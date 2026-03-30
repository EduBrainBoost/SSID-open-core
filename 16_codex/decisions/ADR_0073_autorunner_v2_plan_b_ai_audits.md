# ADR-0073: AutoRunner V2 Plan B — AI-Assisted Audit Modules

**Status:** Accepted
**Date:** 2026-03-16
**Author:** AutoRunner V2 Implementation Team
**Supersedes:** —
**Related:** ADR-0072 (AutoRunner V2 Plan A — Foundation)

---

## Context

AutoRunner V2 Plan A (ADR-0072) established the deterministic foundation modules
(AR-02, AR-05, AR-07, AR-08). Plan B extends this with 6 AI-assisted audit
AutoRunners that require Claude agent integration for borderline cases, deep
analysis, and quarterly compliance reporting.

New GitHub Actions workflow files are added for each Plan B module:
- `.github/workflows/evidence_anchoring.yml` (AR-03)
- `.github/workflows/dora_incident_plan_gate.yml` (AR-04)
- `.github/workflows/pii_scanner.yml` (AR-01)
- `.github/workflows/fee_distribution_audit.yml` (AR-10)
- `.github/workflows/bias_fairness_audit.yml` (AR-09)
- `.github/workflows/doc_generation.yml` (AR-06)

Per the ADR-Pflicht rule: any change to `.github/workflows/` requires a
corresponding ADR in `16_codex/decisions/ADR_*.md`.

---

## Decision

Implement 6 AI-assisted AutoRunner modules following Ansatz C (Hybrid Layered):
deterministic Python checks first, then optional EMS Gate-Runner HTTP call for
Claude agent invocation only when needed.

### Modules Implemented

| AR | Name | Trigger | Agent | Model |
|----|------|---------|-------|-------|
| AR-01 | pii_scanner | push/PR | SEC-05 | Opus (borderline only) |
| AR-03 | evidence_anchoring | hourly cron | OPS-08 | Haiku (errors only) |
| AR-04 | dora_incident_plan_gate | weekly Mon | CMP-14 | Sonnet (missing plans) |
| AR-06 | doc_generation | push main | DOC-20 | Haiku (complex charts) |
| AR-09 | bias_fairness_audit | quarterly | ARS-29 | Opus (analysis) |
| AR-10 | fee_distribution_audit | quarterly | CMP-14 | Sonnet (gaps) |

### Hard Rules Enforced (per Plan B specification)

1. **No fake reports** — all scripts perform real checks against actual files
2. **No stub-successes** — green status requires real evidence
3. **No PII export** — pii_scanner output stores only hash + position, never values
4. **No new root structures** — all files under existing ROOT-24 directories
5. **No cross-branch changes** — implemented exclusively on `feat/autorunner-v2-plan-b-ai-audits`
6. **Docs from actual results** — doc_generation renders real module.yaml content

### Key Technical Decisions

**AR-03 Merkle tree:** SHA-256 of sorted-pair concatenation for deterministic
canonical hashing. `dry_run` when queue is empty (no blockchain call needed).

**AR-04 DORA gate:** Exits 1 (FAIL_DORA) when any of 24 roots lacks
`docs/incident_response_plan.md`. Content validation requires >= 5 Markdown
sections. Agent-CMP creates stubs only as patches, never direct commits.

**AR-01 PII scanner:** RFC 2606 test domains (`@example.com/org/net`) excluded
as false positives. Output JSON stores only `match_length` and `col_start`,
never the actual matched string.

**AR-10 fee audit:** 7-Säulen must sum to exactly 2.00% (tolerance: 0.001).
Subscription model: 50/30/10/10 = 100%. POFI formula validated with
reference vectors including monotonicity check.

**AR-09 bias audit:** Quarterly guard prevents double-run via `quarter_key`
field in state file. Demographic parity max diff <= 0.05, equal opportunity
min TPR >= 0.95.

**AR-06 doc generation:** Uses `ChainableUndefined` Jinja2 environment for
safe handling of missing YAML keys. Output is idempotent (same source hash
→ same output hash).

---

## Consequences

**Positive:**
- 6 new compliance check workflows enforce SoT rules automatically
- All 6 modules have full test coverage (4–6 tests each, 30 total)
- Policy YAML files upgraded from placeholders to real SoT content
- Full TEMPLATE_INCIDENT_RESPONSE.md with 7 sections replaces stub

**Negative:**
- 6 additional workflow runs per trigger (cost: minimal, all fast)
- quarterly audits (AR-09, AR-10) run only 4x/year — low frequency

**Neutral:**
- ADR-Pflicht satisfied for all 6 new workflow files
- ROOT-24-LOCK maintained (no new root directories created)
- Scope allowlist compliance verified (all files under allowed prefixes)
