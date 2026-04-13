# Phase 3a: Root Cleanup — Detailed Plan

**Status**: READY FOR EXECUTION (requires explicit approval)  
**Date**: 2026-04-13

---

## Overview

Phase 3a will remove content from 19 denied roots to enforce the 5-root export boundary.

**Action**: Delete all Python/implementation files from denied roots.  
**Keep**: README.md, module.yaml, empty scaffold directories.  
**Result**: Denied roots become empty scaffolds (10-20 files max, all documentation).

---

## Analysis Summary

| Root | Current | Code Files | Recommendation |
|------|---------|-----------|-----------------|
| 01_ai_layer | 212 files | 1 (.py test) | DELETE .py files, KEEP README.md/module.yaml |
| 02_audit_logging | 222 files | 4 (.py tests) | DELETE .py files |
| 04_deployment | 212 files | 1 (.py test) | DELETE .py files |
| 05_documentation | 212 files | 1 (.py test) | DELETE .py files |
| 06_data_pipeline | 212 files | 1 (.py test) | DELETE .py files |
| 07_governance_legal | 222 files | 4 (.py tests) | DELETE .py files |
| 08_identity_score | 212 files | 1 (.py test) | DELETE .py files |
| 09_meta_identity | 222 files | 4 (.py tests) | DELETE .py files |
| 10_interoperability | 212 files | 1 (.py test) | DELETE .py files |
| 11_test_simulation | 229 files | 8 (.py test/export) | DELETE .py files (tests move to 12_tooling) |
| 13_ui_layer | 213 files | 1 (.py test) | DELETE .py files |
| 14_zero_time_auth | 212 files | 1 (.py test) | DELETE .py files |
| 15_infra | 212 files | 1 (.py test) | DELETE .py files |
| 17_observability | 215 files | 4 (.py tests) | DELETE .py files |
| 18_data_layer | 212 files | 1 (.py test) | DELETE .py files |
| 19_adapters | 212 files | 1 (.py test) | DELETE .py files |
| 20_foundation | 212 files | 1 (.py test) | DELETE .py files |
| 21_post_quantum_crypto | 212 files | 1 (.py test) | DELETE .py files |
| 22_datasets | 212 files | 1 (.py test) | DELETE .py files |

**Total Code Files to Remove**: ~42 files  
**Total Files After Cleanup**: Expected 10-20 per root (documentation only)

---

## Safe Execution Steps

### 3a-1: Backup (Before any deletions)
```bash
tar -czf /backup_denied_roots_2026_04_13.tar.gz \
  01_ai_layer/ 02_audit_logging/ 04_deployment/ ... 22_datasets/
```

### 3a-2: Git Initial State
```bash
git status  # Verify clean state
git log --oneline -1  # Record commit before cleanup
```

### 3a-3: Delete .py Files (but NOT __init__.py)
```bash
# For each denied root:
for root in 01_ai_layer 02_audit_logging ... 22_datasets; do
  find "$root" -name "*.py" ! -name "__init__.py" -type f -delete
done
```

### 3a-4: Verify Cleanup
```bash
# Run validation — should show "All denied roots are empty"
python 12_tooling/scripts/validate_public_boundary.py
```

### 3a-5: Git Commit
```bash
git add -A
git commit -m "Phase 3a: Remove content from denied roots

Enforce 5-root export boundary by removing Python/implementation
files from 19 denied roots. Denied roots now contain only
documentation (README.md, module.yaml).

Roots cleaned: 01_ai_layer, 02_audit_logging, ... 22_datasets
Files removed: ~42 Python test/scaffold files
Result: Validation pass (denied roots empty)

References:
- ADR-0019, ADR-0020, EXPORT_BOUNDARY.md
- validate_public_boundary.py: check [5] passes

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>"
```

### 3a-6: Verify Validation
```bash
python 12_tooling/scripts/validate_public_boundary.py
# Expected: "[5] All denied roots are empty"
```

---

## Approval Checklist

Before executing Phase 3a, confirm:

- [ ] Backup created and verified (tar.gz exists)
- [ ] Git state clean (git status returns "working tree clean")
- [ ] Latest commit recorded (for rollback if needed)
- [ ] Validation script ready (validate_public_boundary.py exists)
- [ ] Phase 2 completion verified (all ADRs and docs committed)
- [ ] Repository clean and ready for destructive operations

---

## Rollback Plan

If cleanup causes issues:

1. **Restore from backup**:
   ```bash
   tar -xzf /backup_denied_roots_2026_04_13.tar.gz
   ```

2. **Reset git**:
   ```bash
   git reset --hard HEAD~1  # Undo Phase 3a commit
   ```

3. **Investigate**: Review what was wrong; update Phase 3a plan

---

## Next Phase (3b-3d)

After 3a completes successfully:
- **3b**: Run full export validation pipeline
- **3c**: Generate public_export_manifest.json
- **3d**: Create PR with Phase 2+3 results

---

**Ready for execution upon approval.**

