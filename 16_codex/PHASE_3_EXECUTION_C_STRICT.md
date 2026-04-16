---
title: Phase 3 Execution — C-STRICT (Custom Deterministic Cleanup)
phase: 3
date: 2026-04-16
status: EXECUTING
---

# Phase 3: C-STRICT Execution Strategy

## Decision Summary

**Strategy**: CUSTOM = C-STRICT (Deterministic Parallel Cleanup with Isolation)
**Rationale**:
- ✅ Deterministisch (pfadbasiert, nicht kategorialisiert)
- ✅ Auditierbar (sequenzielle Integrationsmerges)
- ✅ Konfliktarm (isolierte Worktrees pro Agent)
- ✅ Schnell (Batch 2 parallelisiert nur wo sauber möglich)
- ✅ SSID-kompatibel (ROOT-24-LOCK, SAFE-FIX, Session-Isolation)

## Execution Flow

### **BATCH 1: Manual Sequential Cleanup (3.1 + 3.2)**

**Tasks**: Private repo references + Absolute local paths
**Total Files**: 13
**Effort**: 2-3 Stunden
**Method**: Manual, seriell
**Branch**: main (direct commits)
**Risk**: ✅ MINIMAL

#### Task 3.1: Remove Private Repo References (7 files)
Files to clean:
- `12_tooling/tests/export/test_export_pipeline.py`
- `12_tooling/scripts/validate_hash_manifest.py`
- `12_tooling/scripts/phase9_execute_option_a.py`
- `12_tooling/cli/artifact_drift_gate_v2.py`
- `12_tooling/cli/docs/AUTOMATION_LOOP_RUNBOOK.md`
- `12_tooling/cli/_lib/canonical_paths.py`
- `24_meta_orchestration/dispatcher/e2e_dispatcher.py`

Actions:
- Remove references to: local-workspace, local-config, local-dev, local-test
- Replace with generic descriptions or remove context entirely
- Run local validator after each fix

#### Task 3.2: Replace Absolute Local Paths (6 files)
Files to clean:
- `12_tooling/cli/orchestrator_truth_gate.py`
- `12_tooling/scripts/validate_hash_manifest.py`
- `12_tooling/cli/docs/AUTOMATION_LOOP_RUNBOOK.md`
- `12_tooling/cli/docs/STABILITY_GATE_RUNBOOK.md`
- `16_codex/TESTNET_STATUS.md`
- Additional paths in other docs

Actions:
- Replace absolute system paths with relative paths (`./`, `../`, etc.)
- Replace workspace references with environment variables like `${HOME}`
- Update runbooks to use `$HOME`, `$PWD`, or relative path conventions
- Run local validator after each fix

#### Batch 1 Success Criteria
```bash
python 12_tooling/scripts/validate_public_boundary.py --verify-all
# Expected: Private repo references: 0
# Expected: Absolute local paths: 0
```

---

### **BATCH 2: Parallel Root-Group Cleanup (3.4 Denied Roots)**

**Task**: Scaffold denied roots (3,115 files)
**Method**: 4 Agents, path-based isolation
**Branches**: cleanup/batch2-rootgroup-A/B/C/D (no main writes)
**Worktrees**: Each agent isolated (separate .git worktree)
**Effort**: 4-6 Stunden (parallel)
**Risk**: ✅ LOW (path-based isolation, no cross-agent writes)

#### Root-Group Sharding (Deterministic Path-Based)

**Agent A (Batch2-A)**: Documentation & Data Pipeline
- Roots: `05_documentation/`, `06_data_pipeline/`
- Branch: `cleanup/batch2-rootgroup-a`
- Worktree: Isolated, lock-protected
- Scope: ONLY these 2 roots

**Agent B (Batch2-B)**: Governance, Identity, Metadata
- Roots: `07_governance_legal/`, `08_identity_score/`, `09_meta_identity/`
- Branch: `cleanup/batch2-rootgroup-b`
- Worktree: Isolated, lock-protected
- Scope: ONLY these 3 roots

**Agent C (Batch2-C)**: Interoperability, Tests, UI
- Roots: `10_interoperability/`, `11_test_simulation/`, `13_ui_layer/`
- Branch: `cleanup/batch2-rootgroup-c`
- Worktree: Isolated, lock-protected
- Scope: ONLY these 3 roots

**Agent D (Batch2-D)**: Auth, Infrastructure, Observability, Other
- Roots: `14_zero_time_auth/`, `15_infra/`, `17_observability/`, `18_data_layer/`, `19_adapters/`, `20_foundation/`, `21_post_quantum_crypto/`, `22_datasets/`, `23_compliance/`
- Branch: `cleanup/batch2-rootgroup-d`
- Worktree: Isolated, lock-protected
- Scope: ONLY these 9 roots (rest of denied roots)

#### Batch 2 Agent Actions (Each Agent Parallel)
1. Create worktree: `git worktree add cleanup/batch2-rootgroup-X`
2. Create branch: `cleanup/batch2-rootgroup-X` from origin/main
3. For each root in scope:
   - Delete all files except README.md
   - Keep empty/stub __init__.py only
   - Verify root <10 KB post-cleanup
   - Create SAFE-FIX evidence (SHA256 before/after)
4. Commit atomically with evidence links
5. Push to origin (cleanup/batch2-rootgroup-X)
6. **DO NOT MERGE** — wait for sequential integration

#### Batch 2 Integration (Sequential Merge to main)
After all 4 agents complete:
1. Create integration branch: `cleanup/batch2-integration`
2. Merge Agent A's cleanup branch → integration
3. Run local validator
4. Merge Agent B's cleanup branch → integration
5. Run local validator
6. Merge Agent C's cleanup branch → integration
7. Run local validator
8. Merge Agent D's cleanup branch → integration
9. Run local validator
10. Merge integration → main
11. Run remote boundary gate (expect: 0 denied root violations)

#### Batch 2 Success Criteria
```bash
python 12_tooling/scripts/validate_public_boundary.py --verify-all
# Expected: Denied root violations: 0
# Expected: All denied roots <10 KB
```

---

### **BATCH 3: Manual/Agent Mainnet Claims Cleanup (3.3)**

**Task**: Contextualize 66 unbacked mainnet claims
**Method**: Manual or max 2 Agents (docs-only sharding)
**Branch**: main (direct commits or feature branch)
**Effort**: 4-6 Stunden
**Risk**: ⚠️ MODERATE (semantic cleanup, not structural)
**Timing**: AFTER Batch 2 completes

#### Mainnet Claim Validation Rules
Allowed contexts (per validator):
- "testnet" — explicitly testing, not mainnet
- "planned" — future capability, not current
- "future" — not yet implemented
- "will" — forward-looking, not current
- URLs (http://, https://) — linked to reference
- "reference", "link" — documentation reference

Actions:
1. For each of 66 mainnet/production/live claims:
   - Add contextual keywords if applicable
   - Remove unsupported claims (no reference)
   - Link to TESTNET_STATUS.md for clarity
2. Run local validator after cleanup
3. Commit with rationale

#### Batch 3 Success Criteria
```bash
python 12_tooling/scripts/validate_public_boundary.py --verify-all
# Expected: Unbacked mainnet claims: 0
```

---

### **BATCH 4: Final Verification & Sealed Push (3.5 + Gates)**

**Task**: Verify 24_meta_orchestration forbidden subpaths removed + all gates
**Method**: Manual (read-only verification)
**Branch**: main (no changes, read-only)
**Effort**: 1-2 Stunden
**Risk**: ✅ NONE (verification only)
**Timing**: AFTER Batch 1, 2, 3 complete

#### Checks
1. **Forbidden Subpaths Verification**
   ```bash
   git ls-tree -r HEAD | grep -E "24_meta_orchestration/(registry|tsar|incident|triggers|version_management)"
   # Expected: (empty)
   ```

2. **Local Boundary Validator**
   ```bash
   python 12_tooling/scripts/validate_public_boundary.py --verify-all
   # Expected exit code: 0 (0 violations)
   ```

3. **Boundary Tests**
   ```bash
   pytest 12_tooling/tests/ -k "boundary" -v
   # Expected: All tests pass
   ```

4. **Remote Gates (after push)**
   - Boundary Gate: PASS (0 violations)
   - Export Pipeline: PASS (export succeeds)
   - Drift Detection: PASS (no drift)
   - Security Gates: PASS (no secrets, no private refs)

#### Batch 4 Success Criteria
```
✅ Forbidden subpaths: Not present
✅ Local validator: Exit code 0
✅ Boundary tests: All pass
✅ Remote gates: All green
✅ Violation count: 0 (final)
```

---

## Hard Rules for C-STRICT Execution

| Rule | Enforcement |
|------|-------------|
| No parallel writes to main | STRICT — cleanup branches only, sequential merges |
| One agent = one branch = one scope | STRICT — Agent A cannot write to Agent B's roots |
| Batch 2 parallelization by path only | STRICT — Not by violation category |
| Batch 3 not heavily parallelized | STRICT — Max 2 agents, docs-only sharding |
| Sequential integration merges | STRICT — Merge A → integration, validate, merge B, etc. |
| Local validator after each merge | STRICT — Catch violations early, fail fast |
| Final push only at 0 violations | STRICT — No "acceptable" violations, no "will fix later" |

---

## Batch Execution Schedule

| Batch | Task | Effort | Parallel? | Status |
|-------|------|--------|-----------|--------|
| **1** | 3.1 + 3.2 (13 files) | 2-3h | No | 🔄 READY |
| **2** | 3.4 (3,115 files, 4 roots) | 4-6h | Yes (4 agents) | 🔄 READY |
| **3** | 3.3 (66 claims) | 4-6h | Limited | 🔄 READY (after B2) |
| **4** | 3.5 + Gates | 1-2h | No | 🔄 READY (after B3) |
| | **TOTAL** | **11-17h** | **Parallel B2 = ~8-10h real time** | |

---

## Batch 1 Execution (NEXT)

**Status**: READY_TO_EXECUTE
**Executor**: Manual (Orchestrator role)
**Files**: 13 (7 private refs + 6 absolute paths)
**Expected Outcome**: 0 violations in both categories after cleanup
**Timeline**: Start immediately after this plan approval

---

**Co-Authored-By**: Claude Haiku 4.5 — C-STRICT Execution Planning
