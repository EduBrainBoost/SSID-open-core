---
title: Phase 3 — Public Safety Cleanup & Validation
phase: 3
date: 2026-04-16
status: PLAN_READY
---

# Phase 3: Public Safety Cleanup & Validation

## Overview
Phase 2 (remediation) identified 3,194 boundary violations. Phase 3 resolves all violations and validates gates return green before public release.

## Violation Inventory (R5 Remote Gate Results)

### Category 1: Private Repository References (7 violations)
**Files**:
- `12_tooling/tests/export/test_export_pipeline.py`
- `12_tooling/scripts/validate_hash_manifest.py`
- `12_tooling/scripts/phase9_execute_option_a.py`
- `12_tooling/cli/artifact_drift_gate_v2.py`
- `12_tooling/cli/docs/AUTOMATION_LOOP_RUNBOOK.md`
- `12_tooling/cli/_lib/canonical_paths.py` (partial)
- `24_meta_orchestration/dispatcher/e2e_dispatcher.py`

**Action**: Remove or sanitize references to private repos (local-workspace, local-config, etc.)

### Category 2: Absolute Local Paths (6 violations)
**Files**:
- `12_tooling/cli/orchestrator_truth_gate.py` (absolute paths)
- `12_tooling/scripts/validate_hash_manifest.py` (absolute paths)
- `12_tooling/cli/docs/AUTOMATION_LOOP_RUNBOOK.md` (absolute paths)
- `12_tooling/cli/docs/STABILITY_GATE_RUNBOOK.md` (absolute paths)
- `16_codex/TESTNET_STATUS.md` (absolute paths)
- Additional in docs/

**Action**: Replace absolute paths with relative paths or environment-agnostic references

### Category 3: Unbacked Mainnet Claims (66 violations)
**Files**:
- `12_tooling/README.md:18` (mainnet claim without proof)
- `12_tooling/cli/security/README.md:101` (mainnet claim)
- `12_tooling/cli/security/README.md:266` (mainnet claim)
- `16_codex/PHASE_3_COMPLETION_REPORT.md:93` (unbacked claim)
- `16_codex/PHASE_3_COMPLETION_REPORT.md:127` (unbacked claim)
- 61 additional mainnet claims across docs

**Action**: Remove unbacked mainnet claims or add testnet-only context (per validator logic: allowed if "testnet", "planned", "future", "will" in context)

### Category 4: Denied Root Violations (3,115 violations)
**Roots with excessive content**:
- `05_documentation/` — 473 KB (expected: <10 KB, README.md only)
- `06_data_pipeline/` — manifest, Python, YAML files
- `07_governance_legal/` — policy documents
- `08_identity_score/` — implementation files
- ... and 13 other denied roots
- `24_meta_orchestration/` forbidden subpaths: removed in Phase 2, but some nested content remains

**Action**: Reduce to scaffold-only (README.md + minimal __init__.py stubs per root)

## Phase 3 Cleanup Tasks

### Task 3.1: Remove Private Repo References (P0)
**Effort**: 2-4 hours
**Files**: 7 files in 12_tooling/ and 24_meta_orchestration/
**Actions**:
1. Scan for PRIVATE_REPO_PATTERNS (regex in validator)
2. Replace references with generic paths or remove context entirely
3. Update docstrings to remove workspace-local references
4. Run local validator to confirm fixes

**Success Criteria**: 0 private repo reference violations

### Task 3.2: Replace Absolute Local Paths (P0)
**Effort**: 1-2 hours
**Files**: 6 files in 12_tooling/ and 16_codex/
**Actions**:
1. Identify absolute path patterns (${HOME}, ${SSID_ROOT}, etc.)
2. Replace with relative paths (../../../, ./config, etc.) or environment vars
3. Update runbooks to use portable path conventions
4. Run local validator to confirm fixes

**Success Criteria**: 0 absolute local path violations

### Task 3.3: Contextualize Mainnet Claims (P1)
**Effort**: 4-6 hours
**Files**: 66 files (mostly docs)
**Actions**:
1. Audit each mainnet/production/live claim in exported roots
2. Add testnet context if applicable (validator allows: "testnet", "planned", "future", "will")
3. Remove unbacked claims (no factual basis)
4. Link to TESTNET_STATUS.md for clarity on readiness
5. Run local validator to confirm fixes

**Success Criteria**: 0 unbacked mainnet claims (or all properly contextualized)

### Task 3.4: Scaffold Denied Roots (P0)
**Effort**: 4-8 hours
**Files**: 3,115 files across 19 denied roots + 24_meta_orchestration subpaths
**Actions**:
1. For each denied root (01_ai_layer, 02_audit_logging, 04_deployment, etc.):
   - Keep README.md (scaffold indicator)
   - Keep empty/stub __init__.py files only
   - Delete all other files (Python, YAML, JSON, shell, markdown, text)
2. Create backups before deletion (for audit trail)
3. Verify each root <10 KB post-cleanup
4. Run local validator to confirm fixes

**Success Criteria**: 0 denied root violations, all denied roots scaffold-only

### Task 3.5: Verify 24_meta_orchestration Forbidden Subpaths Removed (P0)
**Effort**: 1 hour
**Files**: registry, tsar, incident, triggers, version_management subpaths
**Actions**:
1. Confirm Phase 2 deletions are present (e.g., `git log --oneline` shows deletion)
2. Verify `git ls-tree -r HEAD` does NOT show these paths
3. Run local validator to confirm 0 violations in 24_meta_orchestration forbidden subpaths

**Success Criteria**: Forbidden subpaths not present in repo

## Phase 3 Validation Gates (Re-Run on Clean Repo)

After cleanup tasks complete:

### Gate 3.1: Local Boundary Validator
```bash
python 12_tooling/scripts/validate_public_boundary.py --verify-all
```
**Expected Result**: Exit code 0 (0 violations)

### Gate 3.2: Remote Boundary Gate
Push to origin/main and verify GitHub Actions boundary_gate.yml returns **PASS**:
- No private repo references
- No absolute paths
- No unbacked mainnet claims
- No denied root violations

### Gate 3.3: Export Pipeline
Verify Public Export Pipeline executes successfully:
- Creates ssid_open_core_export/ artifact
- 3,033 files exported (5 exported roots only)
- No private content in export

### Gate 3.4: Drift Detection
Verify Drift Detection gate passes:
- No files outside exported roots in export
- No divergence from policy

## Phase 3 Success Criteria

| Gate | Current | Target | Status |
|------|---------|--------|--------|
| Private Repo References | 7 | 0 | ⏳ |
| Absolute Local Paths | 6 | 0 | ⏳ |
| Unbacked Mainnet Claims | 66 | 0 | ⏳ |
| Denied Root Violations | 3,115 | 0 | ⏳ |
| **TOTAL VIOLATIONS** | **3,194** | **0** | ⏳ |
| Boundary Gate | FAIL | **PASS** | ⏳ |
| Export Pipeline | FAIL | **PASS** | ⏳ |
| Drift Detection | FAIL | **PASS** | ⏳ |

## Phase 3 Execution Strategy

### Option A: Automated Cleanup (Agent Delegation)
- Spawn 4 parallel cleanup agents (one per violation category)
- Each agent: scan, replace/delete, verify locally, commit atomically
- Merge all cleanup commits to main sequentially
- Re-run remote gates on cleaned main

### Option B: Manual Targeted Cleanup
- Prioritize P0 violations (private refs, absolute paths, denied roots)
- Address P1 violations (mainnet claims) separately
- Sequential commits per task (3.1 → 3.2 → 3.3 → 3.4 → 3.5)
- Final verification push to main

### Option C: Hybrid (Recommended)
- Use agent delegation for denied root cleanup (3.4, largest task)
- Manual targeted cleanup for smaller categories (3.1, 3.2, 3.3)
- Verification and re-gate execution orchestrated

## Next Phase (Phase 4)

After Phase 3 cleanup + gate verification:
- ✅ All gates: PASS
- ✅ Violation count: 0
- ✅ Repository: public-safe

**Phase 4: Production Release Readiness**
- Tag version (v1.0.0-rc3)
- Create GitHub Release
- Publish to public artifact registry
- Final mainnet approval gates

---

## Phase 3 Status

**Status**: PLAN_READY
**Execution Method**: [Awaiting user direction — Automated/Manual/Hybrid]
**Estimated Effort**: 11-20 hours (parallelizable)
**Blocking Items**: None
**External Blockers**: None

Ready to execute when user approves execution strategy.

**Co-Authored-By**: Claude Haiku 4.5 — Phase 3 Planning
