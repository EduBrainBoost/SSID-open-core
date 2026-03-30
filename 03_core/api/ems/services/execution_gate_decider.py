from ems.services.execution_blocker_codes import (
    APPROVAL_MISSING,
    FREEZE_ACTIVE,
    RELEASE_BLOCK_FAILED,
    RUNTIME_DEPENDENCY_NOT_READY,
    TARGET_LOCKED,
    sort_blocker_codes,
)
from ems.services.execution_runtime_context import ExecutionRuntimeContext


def evaluate_execution_gate(context: ExecutionRuntimeContext) -> dict[str, object]:
    blocker_codes: list[str] = []
    if context.active_run_id:
        blocker_codes.append(TARGET_LOCKED)
    if context.approval_status != "approved":
        blocker_codes.append(APPROVAL_MISSING)
    if context.freeze_level in {"soft_freeze", "hard_freeze", "emergency_stop"}:
        blocker_codes.append(FREEZE_ACTIVE)
    if context.release_block_status != "PASS":
        blocker_codes.append(RELEASE_BLOCK_FAILED)
    if context.runtime_dependency_status != "PASS":
        blocker_codes.append(RUNTIME_DEPENDENCY_NOT_READY)
    blocker_codes = sort_blocker_codes(blocker_codes)
    return {
        "decision": "PASS" if not blocker_codes else "BLOCK",
        "blocker_codes": blocker_codes,
        "context": context,
    }
