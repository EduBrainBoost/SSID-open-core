---
title: Phase 4 Implementation Plan — Export Test Migration
date: 2026-04-13
status: READY_FOR_APPROVAL
scope: Move export tests from denied root to exported root
---

# Phase 4: Export Test Migration Implementation Plan

## Objective

Complete test reorganization per ADR-0020 by moving export validation tests from `11_test_simulation` (denied root) to `12_tooling/tests/export/` (exported root).

**Trigger:** Phase 3 completion approval from canonical SSID project lead

---

## Current State (Post-Phase 3)

### Test Location: 11_test_simulation (DENIED ROOT)
```
11_test_simulation/
├── __init__.py
├── README.md
├── module.yaml
└── tests_export/               # ← TO BE MOVED
    ├── __init__.py
    ├── test_export_pipeline.py
    ├── test_boundary_validation.py
    └── fixtures/
        ├── exported_roots_sample.tar.gz
        └── denied_roots_sample.tar.gz
```

### Target Location: 12_tooling/tests/export/ (EXPORTED ROOT)
```
12_tooling/
├── tests/
│   ├── export/                 # ← DESTINATION
│   │   ├── __init__.py
│   │   ├── test_export_pipeline.py
│   │   ├── test_boundary_validation.py
│   │   └── fixtures/
│   │       ├── exported_roots_sample.tar.gz
│   │       └── denied_roots_sample.tar.gz
```

---

## Implementation Steps

### Step 1: Create Target Directory Structure
**Command:**
```bash
mkdir -p 12_tooling/tests/export/fixtures
touch 12_tooling/tests/export/__init__.py
```

**Verification:**
```bash
ls -la 12_tooling/tests/export/
# Expected: __init__.py, empty directory ready for files
```

---

### Step 2: Copy Test Files
**Command:**
```bash
# Copy test files
cp 11_test_simulation/tests_export/test_export_pipeline.py 12_tooling/tests/export/
cp 11_test_simulation/tests_export/test_boundary_validation.py 12_tooling/tests/export/

# Copy fixtures
cp -r 11_test_simulation/tests_export/fixtures/* 12_tooling/tests/export/fixtures/
```

**Verification:**
```bash
ls -la 12_tooling/tests/export/
ls -la 12_tooling/tests/export/fixtures/
# Expected: All test files and fixtures present
```

---

### Step 3: Update Test Import Paths

**File:** `12_tooling/tests/export/test_export_pipeline.py`

**Changes Required:**
- Update relative imports from `11_test_simulation` to `12_tooling`
- Verify fixture paths resolve correctly
- Update any hardcoded paths to use relative path references

**Verification:**
```bash
cd 12_tooling/tests/export
python -m pytest test_export_pipeline.py --collect-only
# Expected: All tests collected without import errors
```

---

### Step 4: Update CI Workflows

**File:** `.github/workflows/public_export_integrity.yml`

**Current (Phase 2 fallback):**
```yaml
- name: Run export validation tests
  run: |
    if [ -d "12_tooling/tests/export" ]; then
      python -m pytest 12_tooling/tests/export/ -v
    else
      echo "Tests not yet migrated; skipping (Phase 4 pending)"
    fi
```

**Target (Phase 4 completion):**
```yaml
- name: Run export validation tests
  run: |
    python -m pytest 12_tooling/tests/export/ -v
```

**Verification:**
```bash
grep -A 5 "Run export validation tests" .github/workflows/public_export_integrity.yml
# Expected: Points to 12_tooling/tests/export/
```

---

### Step 5: Update open_core_ci.yml

**File:** `.github/workflows/open_core_ci.yml`

**Current:**
```yaml
# Tests skipped (11_test_simulation is denied root)
```

**Target:**
```yaml
- name: Export validation tests
  run: python -m pytest 12_tooling/tests/export/ -v
```

**Verification:**
```bash
grep -A 5 "export validation" .github/workflows/open_core_ci.yml
# Expected: References 12_tooling/tests/export/
```

---

### Step 6: Cleanup Denied Root

**Command:**
```bash
# Remove test files from denied root (preserve scaffold)
rm -rf 11_test_simulation/tests_export/

# Verify scaffold remains
ls -la 11_test_simulation/
# Expected: __init__.py, README.md, module.yaml only
```

**Safety Check:**
```bash
# Verify no code remains in 11_test_simulation
find 11_test_simulation/ -name "*.py" -not -name "__init__.py" -type f
# Expected: (empty output)
```

---

### Step 7: Validate Tests Pass

**Command:**
```bash
cd SSID-open-core
python -m pytest 12_tooling/tests/export/ -v --tb=short
```

**Expected Output:**
```
collected 5 items

12_tooling/tests/export/test_export_pipeline.py::test_export_manifest PASSED
12_tooling/tests/export/test_export_pipeline.py::test_export_roots PASSED
12_tooling/tests/export/test_boundary_validation.py::test_private_repo_refs PASSED
12_tooling/tests/export/test_boundary_validation.py::test_absolute_paths PASSED
12_tooling/tests/export/test_boundary_validation.py::test_secret_patterns PASSED

======================== 5 passed in 0.34s ========================
```

**Validation Gate:**
```bash
python 12_tooling/scripts/validate_public_boundary.py
# Expected: All gates PASS, private refs: 0, paths: 0, secrets: 0
```

---

### Step 8: Commit Phase 4

**Command:**
```bash
git add 12_tooling/tests/export/
git add .github/workflows/
git add 11_test_simulation/
git commit -m "Phase 4: Export test migration from 11_test_simulation to 12_tooling

Move export validation tests from denied root (11_test_simulation) to exported
root (12_tooling) per ADR-0020. Update CI workflows to reference new location.
Cleanup denied root scaffold.

- Copied test_export_pipeline.py to 12_tooling/tests/export/
- Copied test_boundary_validation.py to 12_tooling/tests/export/
- Updated fixture paths to new location
- Modified public_export_integrity.yml to reference 12_tooling/tests/export/
- Modified open_core_ci.yml to include export validation
- Removed tests_export/ from 11_test_simulation/
- All tests passing, validation gates PASS

Relates-To: ADR-0020

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>"

git push origin main
```

---

## Pre-Phase 4 Checklist

- [ ] Phase 3 approval received from canonical SSID project lead
- [ ] `12_tooling/tests/export/` directory created
- [ ] All test files copied to new location
- [ ] Import paths updated and verified
- [ ] CI workflows updated to reference new location
- [ ] All tests collected successfully (no import errors)
- [ ] All tests passing (green)
- [ ] validate_public_boundary.py reports PASS
- [ ] Cleanup of 11_test_simulation/tests_export/ complete
- [ ] Git commit prepared with clear message
- [ ] Remote backup verified (git push succeeds)

---

## Risk Mitigation

### Rollback Procedure

If Phase 4 execution encounters issues:

**Step 1: Restore from git**
```bash
git reset --hard HEAD~1
```

**Step 2: Verify scaffold integrity**
```bash
ls -la 11_test_simulation/
ls -la 12_tooling/tests/export/
# 11_test_simulation should show only __init__.py, README.md, module.yaml
```

**Step 3: Validate boundary (should show PASS)**
```bash
python 12_tooling/scripts/validate_public_boundary.py
```

---

## Success Criteria

| Criterion | Target | Verification |
|-----------|--------|--------------|
| Tests collected | 5/5 tests found | `pytest --collect-only` |
| Tests passing | 5/5 tests pass | `pytest -v` exit code 0 |
| Import paths | All imports resolve | No import errors in test output |
| Boundary validation | All gates PASS | `validate_public_boundary.py` PASS |
| CI workflows | Both updated | grep confirms references 12_tooling/tests/export/ |
| Denied root clean | Only scaffold remains | ls 11_test_simulation/ shows 3 files max |
| Git commit | Clean push | git push succeeds to origin/main |

---

## Timeline

**Estimated Duration:** 30 minutes total
- Directory setup: 2 min
- File copy and import updates: 10 min
- CI workflow updates: 5 min
- Test validation: 5 min
- Cleanup and commit: 5 min
- Git push and verification: 3 min

---

## Post-Phase 4 State

### Repository Structure (Target)
```
12_tooling/
├── tests/
│   └── export/
│       ├── __init__.py
│       ├── test_export_pipeline.py
│       ├── test_boundary_validation.py
│       └── fixtures/
│           ├── exported_roots_sample.tar.gz
│           └── denied_roots_sample.tar.gz

11_test_simulation/
├── __init__.py
├── README.md
├── module.yaml
└── (empty scaffold, no code)
```

### Validation Status (Target)
```
[1] Private repo references:     [OK] 0 found
[2] Absolute local paths:        [OK] 0 found
[3] Secret patterns:             [OK] 0 found
[4] Unbacked mainnet claims:     [WARN] 43 (same as Phase 3)
[5] Denied roots empty:          [OK] 19/19 confirmed empty
```

### CI Status (Target)
- ✅ public_export_integrity.yml: Tests passing from 12_tooling/tests/export/
- ✅ open_core_ci.yml: Export validation included and passing
- ✅ All export validation tests: PASS

---

## Notes

- This phase is **non-destructive** — copies tests rather than moving, then cleans up source
- All tests must pass before commit
- Boundary validation must show PASS before push
- Rollback is simple (git reset to previous commit)
- No external dependencies or approvals required (once Phase 3 is approved)

---

**Plan Status:** Ready for approval  
**Trigger Condition:** Phase 3 completion approved  
**Dependencies:** Phase 3 must be complete and approved  
**Next Phase:** Phase 5 (Public Release, pending approval)

