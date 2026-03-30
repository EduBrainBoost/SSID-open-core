# SSID Agent Governance Stack - Bootstrap Complete ✅

**Status**: Phase 1-6 Complete | All Components Integrated | Ready for Multi-Agent Deployment

---

## Executive Summary

The SSID Agent Governance Stack enforces strict policy gates on all multi-agent outputs via a **single dispatcher entry point**. Agents work freely within sandboxes; all changes are validated through a deterministic 3-gate chain before being committed.

**Core Philosophy**: *No KI kommt an Regeln vorbei* — All agent modifications compress through dispatcher → allowlist → Policy gate → SoT gate → QA gate → evidence bundle (hash-only).

---

## 🎯 Implementation Checklist

### ✅ Phase 1: Core Infrastructure
- [x] Dispatcher extended with full gate chain (Policy → SoT → QA)
- [x] `12_tooling/cli/run_all_gates.py` with `--dry-run`, policy-only, QA-only flags
- [x] `12_tooling/cli/sot_validator.py` with `--verify-all`, `--scorecard` flags
- [x] Sandbox deterministic structure: `.ssid_sandbox/<task_id>/`

### ✅ Phase 2: Policy & SoT Layer
- [x] `23_compliance/policies/sot/sot_policy.rego` — OPA minimal surface
- [x] `03_core/validators/sot/sot_validator_core.py` — 5 validators (SOT_AGENT_001..005)
- [x] `16_codex/contracts/sot/sot_contract.yaml` — v3.2.0, machine-readable SoT spec
- [x] `02_audit_logging/reports/SOT_MOSCOW_ENFORCEMENT_V3.2.0.md` — enforcement documentation

### ✅ Phase 3: Test & Compliance
- [x] `11_test_simulation/tests_compliance/test_sot_validator.py` — unittest-based
- [x] `24_meta_orchestration/registry/tasks/TASK_BOOTSTRAP_AGENT_STACK.json` — example task spec

### ✅ Phase 4: Agent Governance Docs
- [x] `16_codex/agents/AGENTS.md` — tool-neutral profiles
- [x] `16_codex/agents/WORKFLOW.md` — gate chain orchestration
- [x] `16_codex/agents/FAILURES.md` — append-only incident log
- [x] `16_codex/agents/TOOL_PROFILES/` — claude.md, gemini.md, codex.md, etc.

### ✅ Phase 5: Tool Wrappers
- [x] `12_tooling/wrappers/claude_run.sh`
- [x] `12_tooling/wrappers/codex_run.sh`
- [x] `12_tooling/wrappers/gemini_run.sh`
- [x] `12_tooling/wrappers/kilo_run.sh` (NEW)
- [x] `12_tooling/wrappers/opencode_run.sh` (NEW)

### ✅ Phase 6: Integration & Validation
- [x] Gate chain verified: Policy → SoT → QA
- [x] Evidence-bundle structure: hash-only (no prompts/stdout)
- [x] Duplicate-guard enforced in all SoT artifacts
- [x] No disallowed paths in sandbox copy (`.git`, `node_modules`, `02_audit_logging`)

---

## 🔧 Key Components

### Entry Points

Single Entry Point (CLI):
```
12_tooling/cli/ssid_dispatcher.py
```

Canonical Dispatcher Implementation:
```
24_meta_orchestration/dispatcher/e2e_dispatcher.py
```

### Gate Chain (Deterministic, Hard-Fail)
```
1. Policy Gate
   Command: python3 12_tooling/scripts/deterministic_repo_setup.py policy_gate
   Input: Repo-wide SoT contract
   Output: PASS/FAIL

2. SoT Gate
   Command: python3 12_tooling/cli/sot_validator.py --verify-all
   Input: 5 SoT validators (SOT_AGENT_001..005)
   Output: PASS/FAIL per rule

3. QA Gate
   Command: python3 02_audit_logging/archives/qa_master_suite/qa_master_suite.py --mode minimal
   Input: Test suite
   Output: PASS/FAIL
```

### Evidence Bundle (Deterministic)
```
02_audit_logging/evidence/tasks/{task_id}__{timestamp}/
├── gate_status.json ........................ Gate results (PASS/FAIL, hashes, tree_state_ref)
├── patch.diff ............................. Unified diff of allowed_paths changes
├── manifest.json .......................... Task metadata + SHA256 hashes
├── hash_manifest.json ..................... File hashes of changed artifacts
└── (NO prompts, NO stdout, NO stderr)
```

### Write Gate (Hard-Fail)
- Blocks all writes outside `allowed_paths` (per task spec)
- Enforced via `ensure_paths_within_allowlist()` in dispatcher
- Returns exit code 24 on violation

### Sandbox Isolation
```
.ssid_sandbox/{task_id}/
├── (repo copy, no .git, node_modules, 02_audit_logging)
├── work area for agent
└── patch extracted only from allowed_paths
```

---

## 📋 SoT Rules (Enforced)

| Rule ID | Title | Priority | Validates |
|---------|-------|----------|-----------|
| **SOT_AGENT_001** | Dispatcher is single entry point | MUST | Canonical paths exist + gate chain functional |
| **SOT_AGENT_002** | Agent governance docs exist | SHOULD | AGENTS.md, WORKFLOW.md, FAILURES.md |
| **SOT_AGENT_003** | Data minimization default | MUST | Evidence hash-only (no prompt/stdout persistence) |
| **SOT_AGENT_004** | Canonical SoT artefact paths | MUST | All 6 canonical files present |
| **SOT_AGENT_005** | Duplicate & consistency guard | MUST | No duplicate rule_ids, functions, Rego rules |

---

## 🚀 Usage Examples

### Run Smoke Tests
```bash
cd C:\Users\bibel\Documents\Github\SSID

# SoT validator
python3 12_tooling/cli/sot_validator.py --verify-all

# Gate chain (dry-run)
python3 12_tooling/cli/run_all_gates.py --dry-run

# Generate scorecard
python3 12_tooling/cli/sot_validator.py --scorecard
```

### Agent Execution
```bash
# Via wrapper (Claude)
./12_tooling/wrappers/claude_run.sh 24_meta_orchestration/registry/tasks/TASK_BOOTSTRAP_AGENT_STACK.json

# Via dispatcher (any agent)
python3 24_meta_orchestration/dispatcher/e2e_dispatcher.py --task <task_spec.json> --export-prompt
```

### Patch Application & Validation
```bash
python3 24_meta_orchestration/dispatcher/e2e_dispatcher.py \
  --task 24_meta_orchestration/registry/tasks/TASK_BOOTSTRAP_AGENT_STACK.json \
  --import-diff patch.diff
```

---

## 🔐 Security Properties

| Property | Implementation |
|----------|----------------|
| **Write-Gate** | Hard-fail on paths outside allowlist |
| **Policy Enforcement** | Deterministic static checks (OPA optional) |
| **SoT Integrity** | All rules consistently mapped across 5 artefacts |
| **Evidence Auditability** | Hash-only (no model I/O, no decisions) |
| **Sandbox Isolation** | Separate directory per task, no repo pollution |
| **No Data Exfiltration** | `02_audit_logging` excluded from sandbox copy |
| **Deterministic Verification** | diff, sha256, tree_state_ref reproducible |

---

## 📦 Files Created/Modified

### Created
- `12_tooling/wrappers/kilo_run.sh` (NEW)
- `12_tooling/wrappers/opencode_run.sh` (NEW)

### Modified
- `03_core/validators/sot/sot_validator_core.py` — Replaced with 5 standalone validators
- `12_tooling/cli/sot_validator.py` — Updated to call module functions (not class methods)
- `12_tooling/cli/run_all_gates.py` — Added `--dry-run` support + deterministic gate orchestration

### Already Existed (Verified Complete)
- `24_meta_orchestration/dispatcher/e2e_dispatcher.py`
- `12_tooling/cli/ssid_dispatcher.py`
- `16_codex/agents/AGENTS.md`, `WORKFLOW.md`, `FAILURES.md`
- `23_compliance/policies/sot/sot_policy.rego`
- `16_codex/contracts/sot/sot_contract.yaml`
- `02_audit_logging/reports/SOT_MOSCOW_ENFORCEMENT_V3.2.0.md`
- All test files in `11_test_simulation/tests_compliance/`

---

## ✨ Next Steps (Out of Scope)

1. **CI/CD Integration** — Hook `run_all_gates.py` into GitHub Actions
2. **OPA Server** — Deploy OPA for runtime policy enforcement (optional; static checks fallback)
3. **Evidence Retention** — Archive evidence bundles in immutable storage (e.g., S3 with object lock)
4. **Multi-Tenancy** — Tag evidence by agent identity + timestamp
5. **Audit Dashboarding** — Query evidence bundles for compliance reports

---

## 🎓 Architecture Decision Record

**Q: Why hash-only evidence?**  
A: Prevents accidental exposure of model prompts, training data, or sensitive outputs in logs. Gates validate logic, not I/O.

**Q: Why sandbox per task?**  
A: Isolates concurrent agent work. Prevents cross-contamination. Easy cleanup/retention policy.

**Q: Why dispatcher is single entry point?**  
A: Centralizes all gate logic. Agents can't bypass policy by directly calling gate scripts. Audit trail flows through dispatcher.

**Q: Why deterministic gates (no scorecards)?**  
A: PASS/FAIL gates are reproducible. Numeric scores introduce subjectivity and drift over time.

---

## 📞 Support

- **SoT Contract**: `16_codex/contracts/sot/sot_contract.yaml`
- **Validator Core**: `03_core/validators/sot/sot_validator_core.py`
- **Incident Log**: `16_codex/agents/FAILURES.md` (append-only)
- **Policy Spec**: `23_compliance/policies/sot/sot_policy.rego`

---

**Bootstrap Status**: ✅ COMPLETE  
**Last Updated**: 2026-02-11  
**Version**: v3.2.0
