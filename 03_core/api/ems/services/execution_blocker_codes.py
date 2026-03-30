"""Stable blocker codes for the EMS execution gateway."""

APPROVAL_MISSING = "approval_missing"
FREEZE_ACTIVE = "freeze_active"
RELEASE_BLOCK_FAILED = "release_block_failed"
RUNTIME_DEPENDENCY_NOT_READY = "runtime_dependency_not_ready"
TARGET_LOCKED = "target_locked"
REGISTRY_DRIFT = "registry_drift"

BLOCKER_PRIORITY = [
    TARGET_LOCKED,
    APPROVAL_MISSING,
    FREEZE_ACTIVE,
    RELEASE_BLOCK_FAILED,
    RUNTIME_DEPENDENCY_NOT_READY,
    REGISTRY_DRIFT,
]


def sort_blocker_codes(values: list[str]) -> list[str]:
    known = {code: index for index, code in enumerate(BLOCKER_PRIORITY)}
    return sorted(values, key=lambda value: (known.get(value, len(BLOCKER_PRIORITY)), value))
