---
title: GitHub PR Review Guide — Phase 2–3 Governance Implementation
date: 2026-04-13
scope: Code review instructions for canonical SSID project lead
---

# PR Review Guide: Phase 2–3 Governance Implementation

## Review Checklist

This guide helps the canonical SSID project lead review the Phase 2–3 implementation pull request.

### Pre-Review

- [ ] Clone SSID-open-core repository
- [ ] Checkout main branch (latest commit: ad0e623)
- [ ] Verify git history is clean and all commits are present

### Phase 2: Governance Realignment (4 commits)

#### Commit: dbf89b0 — "Phase 2a-2b: Governance Realignment & Boundary Clarity"

**Files Changed:**
- `16_codex/decisions/ADR_0019_export_boundary_realignment.md` (NEW)
- `16_codex/decisions/ADR_0020_test_simulation_boundary.md` (NEW)
- `16_codex/EXPORT_BOUNDARY.md` (NEW)
- `README.md` (MODIFIED)
- `CONTRIBUTING.md` (MODIFIED)

**Review Points:**
- [ ] ADR-0019 rationale is clear (canonical SSID as SoT)
- [ ] ADR-0020 classifies 11_test_simulation as DENIED with justification
- [ ] EXPORT_BOUNDARY.md accurately reflects canonical policy
- [ ] README.md updated to remove false "empty scaffold" claim
- [ ] CONTRIBUTING.md documents exception process (RFC → ADR → policy)
- [ ] All governance documents align with canonical SSID policy

**Expected Validation:**
- All documents are policy-aligned
- Exception process is clearly documented
- No local deviations from canonical policy remain

---

#### Commit: 243e3c7 — "Phase 2c-2e: CI Consistency & Validation Enhancement"

**Files Changed:**
- `.github/workflows/public_export_integrity.yml` (MODIFIED)
- `12_tooling/scripts/validate_public_boundary.py` (MODIFIED)

**Review Points:**
- [ ] public_export_integrity.yml updated to reference 12_tooling/tests/export/ (per ADR-0020)
- [ ] Fallback logic added for test discovery
- [ ] validate_public_boundary.py now validates all 24 roots
- [ ] Added DENIED_ROOTS constant (matches canonical SSID)
- [ ] Added validate_denied_roots_empty() function
- [ ] Gate [5] validates scaffolds are properly empty
- [ ] CI workflows now consistent between both export pipelines

**Expected Validation:**
- Test references correct (no 11_test_simulation in exported pipeline)
- Validator checks both exported and denied roots
- No CI inconsistencies

---

#### Commit: 9588668 — "Add Phase 2 Completion Report"

**Files Changed:**
- `16_codex/PHASE_2_COMPLETION_REPORT.md` (NEW)

**Review Points:**
- [ ] Completion report documents Phase 2a-2e
- [ ] All blockers (B001–B004) marked as resolved
- [ ] Phase 3 roadmap is clear
- [ ] Status transition documented (NOT_READY_GOVERNANCE_DRIFT → READY_FOR_PHASE_3)

**Expected Validation:**
- Report accurately reflects completion status
- Blockers are genuinely resolved
- Phase 3 plan is ready for execution

---

### Phase 3: Boundary Enforcement (2 commits)

#### Commit: 1f77af1 — "Phase 3: Export Boundary Enforcement — Root Cleanup + Public-Safe Artifact Removal"

**Files Changed:** 189 files changed
- 42 Python files deleted from 19 denied roots
- 145+ internal artifacts deleted from 5 exported roots
- Backup created: `backup_denied_roots_20260413.tar.gz` (297 KB)

**Review Points - Denied Roots Cleanup:**
- [ ] All 19 denied roots have code files deleted
- [ ] Only empty scaffolds remain (__init__.py, README.md, module.yaml)
- [ ] Backup exists and is properly documented
- [ ] Safe cleanup procedure was followed (per PHASE_3a_CLEANUP_PLAN.md)

**Review Points - Exported Roots Sanitization:**
- [ ] 03_core: pipelines/ deleted (content pipeline infrastructure)
- [ ] 12_tooling: security/, orchestrator_truth_gate.py, plans/ deleted (no public CLI impact)
- [ ] 16_codex: agents/, docs/, forensic_salvage_staging/, local_stack/ deleted (only ADRs remain)
- [ ] 23_compliance: jurisdiction_blacklist.yaml deleted (OPA policies remain)
- [ ] 24_meta_orchestration: agent registries, task manifests, plans/ deleted (dispatcher core remains)

**Review Points - Validation:**
- [ ] No private repo references in exported roots (validate_public_boundary.py [1] = PASS)
- [ ] No absolute local paths in exported roots (validate_public_boundary.py [2] = PASS)
- [ ] No secret patterns in exported roots (validate_public_boundary.py [3] = PASS)
- [ ] All denied roots are empty scaffolds (validate_public_boundary.py [5] = PASS)

**Expected Validation:**
- Cleanups are appropriate and targeted
- Backup is present and documented
- Validation gates all PASS
- No over-deletion or under-deletion

---

#### Commit: e2ebda3 — "docs(completion): Phase 3 enforcement final report"

**Files Changed:**
- `16_codex/PHASE_3_COMPLETION_REPORT.md` (NEW)

**Review Points:**
- [ ] Completion report documents Phase 3 execution
- [ ] All cleanup operations listed with results
- [ ] Validation evidence complete
- [ ] Evidence chain (backups, git history) documented

**Expected Validation:**
- Report is comprehensive and accurate
- Evidence chain is complete
- Status correctly reflects work done

---

### Post-Phase Documentation (3 commits)

#### Commit: e386646 — "docs(audit): governance audit outcome summary"

**Review Points:**
- [ ] AUDIT_OUTCOME_SUMMARY.md accurately summarizes findings
- [ ] All 4 critical issues documented and resolved
- [ ] Governance maturity assessment is fair and accurate

---

#### Commit: ad0e623 — "docs(audit): comprehensive governance audit final report"

**Review Points:**
- [ ] GOVERNANCE_AUDIT_FINAL_REPORT.md is comprehensive
- [ ] All findings, resolutions, and validations documented
- [ ] Success criteria table shows completion
- [ ] Final status clearly stated (INTERNAL_COMPLETE_EXTERNAL_BLOCKED)

---

### Overall Review

#### Governance Alignment
- [ ] Export policy matches canonical SSID (5 roots only)
- [ ] ADRs properly document policy decisions
- [ ] EXPORT_BOUNDARY.md is authoritative and clear
- [ ] Exception process is documented
- [ ] No local deviations from canonical policy remain

#### Critical Violations
- [ ] All 4 critical violations are resolved:
  - [ ] Export boundary drift → RESOLVED (canonical policy restored)
  - [ ] 11_test_simulation ambiguity → RESOLVED (ADR-0020 classifies as DENIED)
  - [ ] Denied roots with code → RESOLVED (42 files deleted)
  - [ ] Internal artifacts in exported roots → RESOLVED (145+ files deleted)

#### Validation
- [ ] All critical gates PASS:
  - [ ] Private repo references: 0 violations
  - [ ] Absolute local paths: 0 violations
  - [ ] Secret patterns: 0 violations
  - [ ] Denied roots empty: 19/19 confirmed
- [ ] Non-critical warnings (43 mainnet claims) are acceptable
- [ ] Validation gates all execute successfully

#### Safety & Reversibility
- [ ] Backup created and documented (backup_denied_roots_20260413.tar.gz)
- [ ] Git history preserves all changes (full traceability)
- [ ] All deletions are recoverable
- [ ] SAFE-FIX protocol followed (SHA256, evidence, backup)

#### Documentation Quality
- [ ] All governance documents are clear and complete
- [ ] Phase reports accurately document execution
- [ ] Audit documents provide full context for decision-makers
- [ ] README.md and CONTRIBUTING.md updated to reflect new policies

---

## What to Test

### Validation Gates
```bash
cd SSID-open-core
python 12_tooling/scripts/validate_public_boundary.py
```

Expected output:
```
[1] Checking for private repo references...        [OK] No private repo references
[2] Checking for absolute local paths...           [OK] No absolute local paths
[3] Checking for secrets/keys/tokens...            [OK] No secret patterns
[4] Checking for unbacked mainnet claims...        [WARN] Found 43 mainnet claim(s)
[5] Checking that denied roots are empty...        [OK] All denied roots are empty

=== Boundary Validation Result ===
Total violations: 43
Boundary validation: PASS (warnings only)
```

### Denied Roots Verification
```bash
# Verify all denied roots are empty (only __init__.py, README.md, module.yaml)
for root in 01_ai_layer 02_audit_logging 04_deployment ... 22_datasets; do
  echo "=== $root ===" && ls -la $root | grep -v "__init__.py\|README.md\|module.yaml\|^d"
done
```

Expected: Only `.` and `..` shown (no files)

### Export Pipeline
```bash
python 12_tooling/scripts/build_public_export.py
```

Expected: Manifest generated with 5 exported roots, 19 scaffolded roots

---

## Questions for Reviewer

1. **Policy Alignment:** Do the ADRs and EXPORT_BOUNDARY.md accurately reflect canonical SSID policy?

2. **Governance Consistency:** Are there any outstanding exceptions or special cases that should be documented in ADR form?

3. **Test Migration:** Is ADR-0020's plan to move export tests from 11_test_simulation to 12_tooling/tests/export/ acceptable?

4. **Future Additions:** Does the exception process (RFC → approval → ADR → policy update) work for canonical SSID?

5. **Merge Readiness:** Is the repository ready for merge into SSID-open-core main with this implementation?

---

## Timeline for Review

- **Quick review (15 min):** Read AUDIT_OUTCOME_SUMMARY.md, verify validation passes
- **Standard review (1 hour):** Read all ADRs and governance docs, review key commits
- **Comprehensive review (2+ hours):** Full audit of all 11 commits, test validation gates

---

## Contact

For questions during review, refer to:
- **Technical details:** GOVERNANCE_AUDIT_FINAL_REPORT.md
- **Implementation evidence:** PHASE_3_COMPLETION_REPORT.md
- **Policy decisions:** ADR-0019, ADR-0020, EXPORT_BOUNDARY.md

---

**Review Status:** Ready for external review  
**Branch:** origin/main (ad0e623)  
**Commits:** 11 total (Phase 2–3 implementation + documentation)
