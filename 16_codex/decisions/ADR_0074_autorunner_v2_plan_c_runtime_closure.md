# ADR-0074: AutoRunner V2 Plan C — Runtime Integration Closure

**Status:** Accepted
**Date:** 2026-03-16
**Author:** AutoRunner V2 Implementation Team
**Supersedes:** —
**Related:** ADR-0073 (AutoRunner V2 Plan B), ADR-0072 (Plan A)

---

## Context

Plan B (ADR-0073) delivered 6 deterministic AR modules. Three items were
consciously deferred as P3:
1. EMS-HTTP coupling (AR modules call EMS after deterministic check)
2. Agent-API binding (Claude invocation on FAIL)
3. AR-04 Stub-Patches via EMS worktree
4. AR-03 Blockchain anchoring hook

P3 closes all four.

---

## Decision

### 1. EMS AR Result Event API
`POST /api/autorunner/ar-results` endpoint added to SSID-EMS portal.
AR scripts in CI can POST results via `--ems-url` flag (fire-and-forget,
stdlib urllib, 5s timeout, never blocks gate on EMS unavailability).
Pattern: same blueprint style as `sot_validation_routes.py`.

### 2. EMS Runner Pipeline Wiring
`ssidctl.autorunner.runner._execute_pipeline()` stub replaced with
subprocess invocation of SSID AR scripts via `ar_script_matrix.py`.
Maps AR_IDs (AR-01/03/04/06/09/10) to script paths and default args.
`autorunner_id: str | None` field added to `AutoRunnerRun` model (optional,
backward compatible).

### 3. Claude Agent Invocation on FAIL
`ssidctl.autorunner.agent_invoker.AgentInvoker.invoke_on_fail()` created.
Fires Claude CLI via AI Gateway (subprocess_driver) when AR returns non-PASS.
Gracefully degrades when Claude CLI unavailable. Call site in runner deferred
to P4 (marked with TODO comment).
Maps: AR-01→SEC-05/Opus, AR-03→OPS-08/Haiku, AR-04→CMP-14/Sonnet,
AR-06→DOC-20/Haiku, AR-09→ARS-29/Opus, AR-10→CMP-14/Sonnet.

### 4. AR-04 IRP Stub Creation
`ssidctl.autorunner.irp_stub_creator.IRPStubCreator.create_stubs()` writes
TEMPLATE_INCIDENT_RESPONSE.md to missing IRP paths.
P3: dry_run=True (file writing, no git ops).
P4: dry_run=False adds git worktree + PR creation.

### 5. AR-03 Blockchain Anchoring Hook
`build_merkle_tree.py` accepts optional `--blockchain-url`. When set,
POSTs Merkle root and stores `tx_hash` in result JSON.
CI workflow keeps no `--blockchain-url` → dry_run=True unchanged.
P4: wire real testnet TX with `${{ secrets.BLOCKCHAIN_ANCHOR_URL }}`.

---

## Consequences

**Positive:**
- AR modules fully integrated into EMS runtime (push + pull paths)
- Agent analysis available on FAIL without manual intervention (P4 call site)
- IRP stub creation path unblocked (P4 git worktree extension)
- Blockchain wiring ready for P4 testnet integration

**Negative:**
- `autorunner_id` field added to `AutoRunnerRun` (optional, backward compatible)
- AR scripts import `ems_reporter` via try/except (no hard dependency)

**Deferred to P4:**
- AR-04 git worktree + PR creation (dry_run=False path in irp_stub_creator)
- Real blockchain TX (testnet credentials needed)
- `agent_invoker.invoke_on_fail()` call site wired into runner (TODO comment present)
