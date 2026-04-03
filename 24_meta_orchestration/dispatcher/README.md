# Dispatcher

The canonical dispatcher implementation is located at `03_core/src/dispatcher.py` (Blueprint 4.1).

> **Note (2026-03-30):** As of this audit cycle, `03_core/src/dispatcher.py` is pending
> implementation (Blueprint 4.1 — APPROVAL_REQUIRED). The current runtime entry point is
> `24_meta_orchestration/dispatcher/e2e_dispatcher.py` (end-to-end test harness only).
>
> Status: PENDING_PRODUCTION_SETUP
> Reality-Audit finding: DOC_CLAIM_FALSE resolved — dispatcher.py not yet present in 03_core/src/

## References
- Blueprint 4.1: `03_core/src/dispatcher.py` (target canonical location)
- Current e2e harness: `24_meta_orchestration/dispatcher/e2e_dispatcher.py`
- Dispatcher registry: `24_meta_orchestration/registry/dispatcher_registry.json`
