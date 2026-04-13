---
title: Governance Maintenance Procedures — SSID-open-core
date: 2026-04-13
scope: Operations manual for ongoing governance policy maintenance
---

# Governance Maintenance Procedures

## Overview

This document defines operational procedures for maintaining SSID-open-core governance policy after Phase 2–3 completion.

---

## 1. Policy Amendment Process

### 1.1 Proposing a Policy Change

**Trigger:** Need to modify EXPORT_BOUNDARY.md, ADRs, or contribution rules

**Procedure:**
1. **Create RFC (Request for Comments)** in GitHub Issues
   - Title: `RFC: [Description of change]`
   - Content: Rationale, proposed changes, impact analysis
   - Label: `type/policy-amendment`

2. **Document Rationale**
   - Why is this change needed?
   - What governance rule would it modify?
   - What are the security/compliance implications?
   - How does it affect existing policy?

3. **Invite Review**
   - Tag: `@ssid-governance-lead`, `@open-core-maintainer`, `@compliance-lead`
   - Set review deadline (minimum 5 business days)

### 1.2 Amendment Approval

**Approvers:**
- Canonical SSID Governance Lead (authority on policy)
- SSID-open-core Maintainer (authority on implementation)
- Compliance Lead (authority on security/legal)

**Approval Criteria:**
- ✅ Rationale is clearly documented
- ✅ Impact on existing policy is analyzed
- ✅ No conflicts with canonical SSID policy
- ✅ All three approvers sign off

### 1.3 Amendment Implementation

**Process:**

1. **Create ADR for Amendment**
   ```
   Filename: 16_codex/decisions/ADR_00XX_[amendment_title].md
   Status: Approved (by all three approvers)
   ```

2. **Update EXPORT_BOUNDARY.md**
   - Modify affected sections
   - Add amendment date and reference to ADR
   - Update "Last Modified" date

3. **Update Related Documentation**
   - README.md (if boundary description changes)
   - CONTRIBUTING.md (if process changes)
   - CI workflows (if validation gates change)

4. **Update Validation Rules**
   - Modify 12_tooling/scripts/validate_public_boundary.py if needed
   - Update validation gate definitions
   - Test all gates pass

5. **Commit and Push**
   ```bash
   git add 16_codex/decisions/ADR_00XX_*
   git add 16_codex/EXPORT_BOUNDARY.md
   git add README.md CONTRIBUTING.md
   git add 12_tooling/scripts/validate_public_boundary.py
   git commit -m "policy: amend governance per RFC-XXX / ADR-00XX

   [Description of amendment]
   
   Approved by: Governance Lead, Maintainer, Compliance Lead
   RFC: [Issue #]
   ADR: ADR-00XX"
   git push origin main
   ```

---

## 2. Quarterly Policy Review

### 2.1 Review Schedule

**When:** First Monday of each quarter (Jan 1, Apr 1, Jul 1, Oct 1)  
**Duration:** 4 weeks  
**Owner:** Canonical SSID Governance Lead  

### 2.2 Review Scope

Audit the following for consistency with canonical SSID:

- [ ] EXPORT_BOUNDARY.md is current
- [ ] All ADRs are still valid
- [ ] No policy drift from canonical SSID
- [ ] No undocumented exceptions exist
- [ ] All denied roots remain empty
- [ ] All exported roots remain public-safe
- [ ] CI validation gates all pass
- [ ] No new critical violations detected

### 2.3 Review Procedure

**Step 1: Generate Validation Report**
```bash
cd SSID-open-core
python 12_tooling/scripts/validate_public_boundary.py > VALIDATION_REPORT_Q[N]_2026.txt
git log --oneline -20 > GIT_HISTORY_Q[N]_2026.txt
```

**Step 2: Compare to Baseline**
- Compare current validation to baseline (from FINAL_STATUS_REPORT.md)
- Identify any new violations or drift
- Document changes since last quarter

**Step 3: Policy Audit**
- Review all ADRs created since last quarter
- Verify each ADR was approved by three parties
- Check that EXPORT_BOUNDARY.md reflects all changes

**Step 4: Governance Health Assessment**
- No critical violations: ✅/❌
- All policy amendments documented: ✅/❌
- Denied roots remain empty: ✅/❌
- Exported roots remain clean: ✅/❌
- CI gates all passing: ✅/❌

**Step 5: Publish Quarterly Governance Review**

**File:** `16_codex/governance_reviews/GOVERNANCE_REVIEW_Q[N]_2026.md`

**Content:**
```markdown
---
title: Quarterly Governance Review Q[N] 2026
date: [Date]
period: [Date Range]
status: [COMPLIANT / DRIFT_DETECTED / VIOLATIONS]
---

# Governance Review Q[N] 2026

## Summary
[Overview of governance status]

## Validation Results
[validation_public_boundary.py output]

## Policy Changes
[List of amendments/ADRs created this quarter]

## Issues Detected
[Any drift, violations, or concerns]

## Recommendations
[Any actions needed]

## Sign-Off
Reviewed by: [Governance Lead Name]
Date: [Date]
```

**Step 6: Archive Review**
```bash
mkdir -p 16_codex/governance_reviews/
git add 16_codex/governance_reviews/GOVERNANCE_REVIEW_Q[N]_2026.md
git commit -m "docs(governance): Q[N] 2026 quarterly review"
git push origin main
```

---

## 3. Exception Handling

### 3.1 Temporary Exceptions

**Scenario:** Need to add code to a denied root or internal-use code to exported root temporarily

**Process:**

1. **Create Exception Request**
   - File GitHub issue with label `type/policy-exception`
   - Describe: What code, why needed, expected duration

2. **Document in ADR**
   - Create ADR_00XX_[exception_name]
   - Rationale: Why canonical policy cannot accommodate this
   - Justification: Why temporary exception is acceptable
   - Sunset clause: When/how exception will be removed

3. **Update EXPORT_BOUNDARY.md**
   - Add section: "Active Exceptions"
   - List exception, ADR reference, sunset date

4. **Implement with Safety Measures**
   - Store exception code in separate directory/file
   - Add clear comments: `# EXCEPTION: ADR-00XX`
   - Include sunset date in comment
   - Add validation rule to flag exception on future boundary checks

5. **Quarterly Review Exception**
   - Each quarterly review must verify exception is still valid
   - If sunset date passed, schedule removal
   - If exception becoming permanent, convert to formal amendment

### 3.2 Exception Removal

**When:** Sunset date reached or reason for exception no longer exists

**Process:**

1. **Remove Exception Code**
   ```bash
   # Delete code that was under exception
   git rm [files under exception]
   ```

2. **Update EXPORT_BOUNDARY.md**
   - Remove from "Active Exceptions" section
   - Add to "Completed Exceptions" archive (reference/historical)

3. **Remove Validation Override**
   - Remove validation exception rules
   - Restore full validation for that code area

4. **Commit Removal**
   ```bash
   git commit -m "policy: complete exception cleanup per ADR-00XX
   
   Exception sunset date reached. Removed temporary code and validation
   overrides. Exported boundary fully enforced."
   git push origin main
   ```

---

## 4. Denied Root Restoration

### 4.1 Scenario

New feature needs to be added to a denied root (e.g., new 08_identity_score function).

**Options:**
1. **Propose Amendment** — Reclassify root as exported (requires RFC + ADR)
2. **Move to Exported Root** — Place feature in compatible exported root
3. **Create New Exported Root** — Propose new public API root (requires RFC + ADR + canonical approval)

### 4.2 Process for Option 2: Move to Exported Root

1. **Identify Compatible Root**
   - Review 5 exported roots for best fit
   - 03_core: Validators, primitives
   - 12_tooling: CLI, operational tools
   - 16_codex: Governance, documentation
   - 23_compliance: Policies, rules
   - 24_meta_orchestration: Dispatcher, orchestration

2. **Create RFC**
   - Explain feature and why it belongs in public API
   - Propose target exported root
   - Document rationale

3. **Get Approval**
   - Governance Lead approval
   - Maintainer approval
   - No need for amendment (already approved roots)

4. **Implement in Target Root**
   - Place feature in appropriate exported root
   - Update documentation
   - Run validation (must PASS)

5. **Commit**
   ```bash
   git commit -m "feat: [feature] in 12_tooling [example]
   
   Add new feature to exported root per RFC-XXX.
   Feature placed in 12_tooling instead of denied root
   08_identity_score to maintain export boundary."
   ```

---

## 5. CI/Validation Gate Maintenance

### 5.1 Gate Health Checks

**Weekly Task (every Monday):**
```bash
cd SSID-open-core
python 12_tooling/scripts/validate_public_boundary.py
echo "Exit code: $?"
```

**Expected:** Exit code 0, all critical gates PASS

**If gates fail:**
1. Identify which gate failed
2. Investigate root cause
3. Fix underlying issue (not validation rule)
4. Confirm all gates pass
5. Document incident in incident log

### 5.2 Validation Rule Updates

**When to update validate_public_boundary.py:**
- New secret pattern discovered in wild (add to SECRET_PATTERNS)
- New repository naming convention in organization (add to PRIVATE_REPO_PATTERNS)
- New absolute path pattern to exclude (add to ABSOLUTE_PATH_PATTERNS)
- Validation scope expands (e.g., check for new artifact types)

**Process:**
1. Create GitHub issue documenting reason for rule update
2. Update rule in validate_public_boundary.py
3. Test rule with sample data
4. Verify rule doesn't false-positive on legitimate code
5. Commit with clear rationale
6. Run full validation suite to ensure no regressions

### 5.3 Test Coverage Maintenance

**When:** Each quarterly review + whenever tests are added/modified

**Procedure:**
```bash
cd 12_tooling/tests/export
python -m pytest --cov=12_tooling.scripts.build_public_export --cov=12_tooling.scripts.validate_public_boundary --cov-report=term-missing
```

**Target:** 80%+ coverage of validation logic

**If coverage drops:**
1. Identify uncovered code sections
2. Add tests to cover new code paths
3. Rerun coverage check
4. Commit tests with issue reference

---

## 6. Incident Response

### 6.1 Critical Violation Detected

**If validation gates detect critical violation:**

**Immediate (within 1 hour):**
1. Run: `python 12_tooling/scripts/validate_public_boundary.py`
2. Document findings (what violation, where, when detected)
3. Notify: Governance Lead, Maintainer, Compliance Lead

**Within 4 hours:**
1. Determine root cause (was it introduced by recent commit?)
2. If recent commit caused it: Consider git revert
3. Otherwise: Analyze how violation entered system

**Within 24 hours:**
1. Implement fix (remove violation)
2. Verify all gates pass
3. Create incident report

**Within 1 week:**
1. Publish post-incident review
2. Document lessons learned
3. Identify preventive measures
4. Update procedures if needed

### 6.2 Incident Log

**File:** `16_codex/incidents/INCIDENT_LOG.md`

**Format:**
```markdown
## Incident #1 — [Date]
**Severity:** [Critical/High/Medium/Low]
**Violation:** [What was detected]
**Root Cause:** [How did it happen]
**Resolution Time:** [How long to fix]
**Fix:** [What was done]
**Lessons Learned:** [Prevention measures]

---
```

---

## 7. Documentation Maintenance

### 7.1 Keep Documentation Current

**Every commit that affects governance:**
- [ ] Update EXPORT_BOUNDARY.md if rules changed
- [ ] Update README.md if boundary description changed
- [ ] Update CONTRIBUTING.md if process changed
- [ ] Create/update ADR if policy changed
- [ ] Update CI workflow documentation if gates changed

### 7.2 Annual Documentation Audit

**When:** Each January 1st

**Procedure:**
1. Review all governance documents
2. Check for:
   - Outdated information
   - Broken links
   - Unclear explanations
   - Missing examples
3. Update/improve clarity
4. Commit: `docs: annual governance documentation audit`

---

## 8. Escalation Path

**If uncertain about policy decision:**

1. **Clarification Needed?** → Create GitHub issue, tag `@ssid-governance-lead`
2. **Amendment Needed?** → File RFC issue per section 1.1
3. **Exception Needed?** → File exception request per section 3.1
4. **Emergency?** → Directly notify Governance Lead (contact info in CONTRIBUTING.md)

---

## 9. Key Contacts

| Role | Responsibility | Contact |
|------|-----------------|---------|
| Governance Lead | Policy authority, amendments, reviews | [canonical SSID repo] |
| Maintainer | Implementation, day-to-day ops | [repo CONTRIBUTING.md] |
| Compliance Lead | Security/legal implications | [org compliance team] |

---

**Procedures Version:** 1.0  
**Last Updated:** 2026-04-13  
**Next Review:** 2026-07-01 (Q3 2026)

