"""Tests for EMS Orchestrator — Phase 10."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from ems_orchestrator import EMSOrchestrator, RunStatus, TaskStatus


def test_task_lifecycle():
    ems = EMSOrchestrator()
    task = ems.create_task("Test DID", "phase4", "09_meta_identity", "01_identitaet_personen")
    assert task.status == TaskStatus.PENDING
    ems.assign_task(task.task_id, "agent-01")
    assert task.status == TaskStatus.IN_PROGRESS
    run = ems.start_run(task.task_id, "agent-01")
    assert run.status == RunStatus.RUNNING
    ems.complete_run(run.run_id, {"result": "ok"})
    assert run.status == RunStatus.SUCCESS
    assert task.status == TaskStatus.COMPLETED
    assert task.evidence_hash is not None
    print("PASS: test_task_lifecycle")


def test_emergency_stop():
    ems = EMSOrchestrator()
    task = ems.create_task("Risky Op", "test", "03_core", "01")
    ems.assign_task(task.task_id, "agent-02")
    result = ems.emergency_stop(task.task_id, "policy_violation")
    assert task.status == TaskStatus.CANCELLED
    assert result["action"] == "emergency_stop"
    print("PASS: test_emergency_stop")


def test_run_ledger():
    ems = EMSOrchestrator()
    task = ems.create_task("Ledger Test", "test", "02_audit", "01")
    ems.assign_task(task.task_id, "agent-03")
    run = ems.start_run(task.task_id, "agent-03")
    ems.complete_run(run.run_id, {"data": 123})
    ledger = ems.get_run_ledger()
    assert len(ledger) == 1
    assert ledger[0]["status"] == "success"
    print("PASS: test_run_ledger")


if __name__ == "__main__":
    test_task_lifecycle()
    test_emergency_stop()
    test_run_ledger()
    print("\nALL TESTS PASSED")
