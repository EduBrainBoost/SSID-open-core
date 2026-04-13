# Open-Core Migration Patchset Plan

**Generated:** 2026-03-29
**Status:** PREP-ONLY (no changes applied)
**Authority:** ROOT-24-LOCK + Open-Core Policy
**Target Repository:** SSID-open-core
**Source Repository:** SSID (canonical)

## Summary

| Metric | Count |
|--------|-------|
| Total files before | 5335 |
| Files to remove (denied roots) | 4079 |
| CRITICAL files (Phase 1) | 222 |
| CI workflows to remove | 2 |
| Files remaining after | 1250 |
| Allowed roots | 5 (03, 12, 16, 23, 24) |
| Denied roots | 19 |

---

## Phase 0: Prep (THIS DOCUMENT)

**Scope:** Generate compliance artifacts in SSID (not open-core).
**File count:** 5 new files in `23_compliance/opencore/`
**Risk:** NONE (no changes to open-core)
**Rollback:** Delete `23_compliance/opencore/` directory

### Artifacts
- `deletion_manifest.json` -- 4079 entries, per-file sensitivity classification
- `allowlist.yaml` -- 5 allowed roots with rules, extensions, patterns
- `denylist.yaml` -- 19 denied roots with reasons (IP/WORM/NDA/INFRA)
- `migration_patchset_plan.md` -- this document
- `dry_run_evidence.json` -- simulated migration outcome

---

## Phase 1: CRITICAL_REMOVE

**Scope:** Remove 222 CRITICAL-classified files first (WORM, quarantine, evidence, secrets, audit, tokens, credentials, keys).
**File count:** 222 files
**Risk:** HIGH -- these files must never appear in git history of a public repo
**Rollback:** `git revert` of Phase 1 commit

### Steps
1. Run `deletion_manifest.json` filter for `sensitivity_class == CRITICAL`
2. Verify each file path exists in open-core
3. `git rm` all 222 files in a single atomic commit
4. Verify no CRITICAL patterns remain via `grep -r` scan
5. Evidence hash of commit

### Pre-conditions
- [ ] All prep artifacts reviewed and approved
- [ ] Backup of open-core repository created
- [ ] No open PRs against denied roots

---

## Phase 2: Remove 19 Denied Root Directories

**Scope:** Remove all remaining files in 19 denied roots (4079 - 222 = 3857 files).
**File count:** 3857 files across 19 directories
**Risk:** MEDIUM -- bulk removal, no secrets involved (already removed in Phase 1)
**Rollback:** `git revert` of Phase 2 commit

### Steps
1. `git rm -r` for each of the 19 denied roots:
   - 01_ai_layer (212 files)
   - 02_audit_logging (222 files)
   - 04_deployment (212 files)
   - 05_documentation (225 files)
   - 06_data_pipeline (212 files)
   - 07_governance_legal (220 files)
   - 08_identity_score (212 files)
   - 09_meta_identity (220 files)
   - 10_interoperability (212 files)
   - 11_test_simulation (220 files)
   - 13_ui_layer (213 files)
   - 14_zero_time_auth (212 files)
   - 15_infra (212 files)
   - 17_observability (215 files)
   - 18_data_layer (212 files)
   - 19_adapters (212 files)
   - 20_foundation (212 files)
   - 21_post_quantum_crypto (212 files)
   - 22_datasets (212 files)
2. Single atomic commit
3. Verify only 5 allowed roots remain
4. Evidence hash of commit

### Pre-conditions
- [ ] Phase 1 completed and verified
- [ ] No dependencies from allowed roots into denied roots

---

## Phase 3: Sync Allowed Roots Against SSID Source

**Scope:** Update the 5 allowed roots in open-core to match canonical SSID content.
**File count:** 1237 files across 5 roots
**Risk:** MEDIUM -- content sync, must filter forbidden patterns
**Rollback:** `git revert` of Phase 3 commit

### Steps
1. For each allowed root (03_core, 12_tooling, 16_codex, 23_compliance, 24_meta_orchestration):
   a. Diff open-core vs SSID canonical
   b. Apply `allowlist.yaml` forbidden_patterns filter
   c. Copy updated files
   d. Remove files not present in canonical source
2. Verify no forbidden patterns in synced content
3. Single atomic commit
4. Evidence hash of commit

### Pre-conditions
- [ ] Phase 2 completed
- [ ] allowlist.yaml reviewed and approved
- [ ] No secrets in canonical source files (grep scan)

---

## Phase 4: .github/workflows Anpassen

**Scope:** Remove internal CI workflows, keep open-core-appropriate ones.
**File count:** 2 files to remove, 2 files to keep/update
**Risk:** LOW
**Rollback:** `git revert` of Phase 4 commit

### Steps
1. Remove denied workflows:
   - `.github/workflows/cron_daily_sanctions.yml` (internal sanctions screening)
   - `.github/workflows/cron_quarterly_audit.yml` (internal audit)
2. Keep and review:
   - `.github/workflows/open_core_ci.yml` (update if needed)
   - `.github/workflows/cron_daily_structure_gate.yml` (update root list to 5)
3. Single atomic commit
4. Evidence hash

### Pre-conditions
- [ ] Phase 3 completed
- [ ] CI workflow content reviewed for secret references

---

## Phase 5: README/CONTRIBUTING/LICENSE Aktualisieren

**Scope:** Update root-level documentation for open-core context.
**File count:** ~6 files (README.md, CONTRIBUTING.md, LICENSE, DCO.txt, SECURITY.md, AGENTS.md)
**Risk:** LOW
**Rollback:** `git revert` of Phase 5 commit

### Steps
1. Update README.md:
   - Remove references to denied roots
   - Document 5 allowed roots and their purpose
   - Add open-core contribution guidelines
2. Update CONTRIBUTING.md:
   - Reference allowlist/denylist
   - Explain root restrictions
3. Review LICENSE (Apache-2.0 or similar)
4. Review SECURITY.md for internal references
5. Update CLAUDE.md and AGENTS.md
6. Remove .pytest_cache (generated, should be in .gitignore)
7. Single atomic commit
8. Evidence hash

### Pre-conditions
- [ ] Phase 4 completed
- [ ] Legal review of LICENSE terms

---

## Phase 6: Verifikation

**Scope:** Full verification of open-core repository state.
**File count:** 0 (verification only)
**Risk:** NONE
**Rollback:** N/A

### Steps
1. Structure gate:
   - Verify exactly 5 root directories exist
   - Verify no denied root directories exist
   - Verify root-level files match allowlist
2. Content scan:
   - grep for forbidden patterns (secrets, credentials, keys, tokens)
   - grep for internal references (vault, internal URLs, IP addresses)
   - grep for WORM/evidence/quarantine references
3. Dependency check:
   - Verify no imports from denied roots
   - Verify no cross-references to denied roots
4. CI verification:
   - Run open_core_ci.yml locally
   - Run structure gate locally
5. Generate final evidence report
6. Compare file counts against dry_run_evidence.json

### Success Criteria
- [ ] 5 root directories only
- [ ] 0 forbidden pattern matches
- [ ] 0 denied root references
- [ ] CI passes
- [ ] File count matches prediction (1250 files)

---

## Risk Matrix

| Phase | Risk Level | Impact | Mitigation |
|-------|-----------|--------|------------|
| 0 | NONE | No changes to open-core | N/A |
| 1 | HIGH | Secret/evidence exposure if missed | Double-scan, manual review |
| 2 | MEDIUM | Broken references | Dependency check before remove |
| 3 | MEDIUM | Content drift | Diff review, forbidden pattern filter |
| 4 | LOW | CI disruption | Local test before commit |
| 5 | LOW | Documentation gaps | Review checklist |
| 6 | NONE | Verification only | N/A |

## Global Rollback Plan

If any phase fails critically:
1. `git log` to identify last known-good commit
2. `git revert --no-commit <bad-commit>..HEAD`
3. `git commit -m "revert: rollback to pre-migration state"`
4. Re-run Phase 6 verification against pre-migration baseline

## Notes

- **BFG Repo-Cleaner** or `git filter-repo` MUST be used after Phase 1 to purge CRITICAL files from git history before any public push
- The open-core repo should be treated as a NEW repository (force-push cleaned history) rather than preserving current git history
- All phases require explicit approval before execution (PLAN > APPROVAL > APPLY)
