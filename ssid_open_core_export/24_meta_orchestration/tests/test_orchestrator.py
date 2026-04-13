"""Tests for 24_meta_orchestration/src/orchestrator.py.

Covers:
  - Orchestrator class is importable and instantiable
  - dispatch_task accepts a dict and returns task_id + status
  - dispatch_task with executor callback runs inline
  - dispatch_task with failing executor records FAILED status
  - get_task_status returns correct lifecycle data
  - get_task_status raises KeyError for unknown task_id
  - list_tasks returns all tasks or filtered by status
  - cancel_task transitions cancellable tasks to CANCELLED
  - cancel_task rejects non-cancellable states

SoT v4.1.0 | ROOT-24-LOCK
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def orchestrator_cls():
    from orchestrator import Orchestrator  # type: ignore[import]

    return Orchestrator


@pytest.fixture(scope="module")
def task_status_enum():
    from orchestrator import TaskStatus  # type: ignore[import]

    return TaskStatus


@pytest.fixture()
def orch(orchestrator_cls):
    return orchestrator_cls()


@pytest.fixture()
def echo_executor():
    """Executor that echoes back the task spec as result."""

    def _execute(task_spec: dict) -> dict:
        return {"echoed": task_spec}

    return _execute


@pytest.fixture()
def failing_executor():
    """Executor that always raises an exception."""

    def _execute(task_spec: dict) -> dict:
        raise RuntimeError("Executor failed deliberately")

    return _execute


# ---------------------------------------------------------------------------
# Class availability
# ---------------------------------------------------------------------------


class TestOrchestratorImport:
    def test_orchestrator_importable(self, orchestrator_cls):
        assert orchestrator_cls is not None

    def test_orchestrator_is_class(self, orchestrator_cls):
        assert isinstance(orchestrator_cls, type)

    def test_orchestrator_instantiates(self, orchestrator_cls):
        obj = orchestrator_cls()
        assert obj is not None

    def test_orchestrator_accepts_executor(self, orchestrator_cls, echo_executor):
        obj = orchestrator_cls(executor=echo_executor)
        assert obj is not None


# ---------------------------------------------------------------------------
# dispatch_task — no executor (DISPATCHED status)
# ---------------------------------------------------------------------------


class TestDispatchTaskNoExecutor:
    def test_returns_dict(self, orch):
        result = orch.dispatch_task({"task_id": "TS001"})
        assert isinstance(result, dict)

    def test_returns_task_id(self, orch):
        result = orch.dispatch_task({"task_id": "TS001"})
        assert "task_id" in result
        assert isinstance(result["task_id"], str)
        assert len(result["task_id"]) > 0

    def test_returns_dispatched_status(self, orch):
        result = orch.dispatch_task({"task_id": "TS001"})
        assert result["status"] == "dispatched"

    def test_accepts_empty_dict(self, orch):
        result = orch.dispatch_task({})
        assert "task_id" in result
        assert result["status"] == "dispatched"

    def test_unique_task_ids(self, orch):
        r1 = orch.dispatch_task({"a": 1})
        r2 = orch.dispatch_task({"b": 2})
        assert r1["task_id"] != r2["task_id"]

    def test_dispatch_has_docstring(self, orchestrator_cls):
        assert orchestrator_cls.dispatch_task.__doc__ is not None

    def test_dispatch_docstring_describes_task(self, orchestrator_cls):
        doc = orchestrator_cls.dispatch_task.__doc__ or ""
        assert "task" in doc.lower()


# ---------------------------------------------------------------------------
# dispatch_task — with executor (COMPLETED / FAILED)
# ---------------------------------------------------------------------------


class TestDispatchTaskWithExecutor:
    def test_completed_on_success(self, orchestrator_cls, echo_executor):
        orch = orchestrator_cls(executor=echo_executor)
        result = orch.dispatch_task({"key": "value"})
        assert result["status"] == "completed"

    def test_failed_on_executor_error(self, orchestrator_cls, failing_executor):
        orch = orchestrator_cls(executor=failing_executor)
        result = orch.dispatch_task({"key": "value"})
        assert result["status"] == "failed"

    def test_task_result_stored_on_success(self, orchestrator_cls, echo_executor):
        orch = orchestrator_cls(executor=echo_executor)
        dispatch = orch.dispatch_task({"key": "value"})
        status = orch.get_task_status(dispatch["task_id"])
        assert "result" in status
        assert status["result"]["echoed"]["key"] == "value"

    def test_task_error_stored_on_failure(self, orchestrator_cls, failing_executor):
        orch = orchestrator_cls(executor=failing_executor)
        dispatch = orch.dispatch_task({"key": "value"})
        status = orch.get_task_status(dispatch["task_id"])
        assert "error" in status
        assert "deliberately" in status["error"]


# ---------------------------------------------------------------------------
# get_task_status
# ---------------------------------------------------------------------------


class TestGetTaskStatus:
    def test_returns_dict_for_known_task(self, orch):
        dispatch = orch.dispatch_task({"task_id": "TS002"})
        status = orch.get_task_status(dispatch["task_id"])
        assert isinstance(status, dict)

    def test_status_contains_required_fields(self, orch):
        dispatch = orch.dispatch_task({"task_id": "TS003"})
        status = orch.get_task_status(dispatch["task_id"])
        assert "task_id" in status
        assert "status" in status
        assert "created_at" in status
        assert "updated_at" in status

    def test_raises_key_error_for_unknown_task(self, orch):
        with pytest.raises(KeyError):
            orch.get_task_status("nonexistent-task-id")

    def test_status_has_docstring(self, orchestrator_cls):
        assert orchestrator_cls.get_task_status.__doc__ is not None


# ---------------------------------------------------------------------------
# list_tasks
# ---------------------------------------------------------------------------


class TestListTasks:
    def test_list_all_tasks(self, orch):
        orch.dispatch_task({"a": 1})
        orch.dispatch_task({"b": 2})
        tasks = orch.list_tasks()
        assert isinstance(tasks, list)
        assert len(tasks) >= 2

    def test_list_tasks_filtered(self, orch, task_status_enum):
        orch.dispatch_task({"c": 3})
        tasks = orch.list_tasks(status=task_status_enum.DISPATCHED)
        assert all(t["status"] == "dispatched" for t in tasks)

    def test_list_tasks_empty_filter(self, orch, task_status_enum):
        tasks = orch.list_tasks(status=task_status_enum.RUNNING)
        assert isinstance(tasks, list)


# ---------------------------------------------------------------------------
# cancel_task
# ---------------------------------------------------------------------------


class TestCancelTask:
    def test_cancel_dispatched_task(self, orch):
        dispatch = orch.dispatch_task({"cancel_me": True})
        result = orch.cancel_task(dispatch["task_id"])
        assert result["status"] == "cancelled"

    def test_cancel_updates_status(self, orch):
        dispatch = orch.dispatch_task({"cancel_me": True})
        orch.cancel_task(dispatch["task_id"])
        status = orch.get_task_status(dispatch["task_id"])
        assert status["status"] == "cancelled"

    def test_cancel_completed_raises_value_error(self, orchestrator_cls, echo_executor):
        orch = orchestrator_cls(executor=echo_executor)
        dispatch = orch.dispatch_task({"key": "val"})
        with pytest.raises(ValueError):
            orch.cancel_task(dispatch["task_id"])

    def test_cancel_unknown_raises_key_error(self, orch):
        with pytest.raises(KeyError):
            orch.cancel_task("nonexistent-id")


# ---------------------------------------------------------------------------
# Source-level checks
# ---------------------------------------------------------------------------


class TestOrchestratorSource:
    @pytest.fixture(autouse=True)
    def _src_path(self):
        self.src_path = SRC_DIR / "orchestrator.py"

    def test_source_file_exists(self):
        assert self.src_path.exists(), "orchestrator.py not found in src/"

    def test_source_has_module_docstring(self):
        import orchestrator as _mod  # type: ignore[import]

        assert _mod.__doc__ is not None

    def test_source_mentions_sot_version(self):
        content = self.src_path.read_text(encoding="utf-8")
        assert "SoT" in content or "v4" in content, "orchestrator.py should reference SoT version"

    def test_source_has_no_placeholder_markers(self):
        content = self.src_path.read_text(encoding="utf-8")
        for marker in ["AUTO-GENERATED PLACEHOLDER", "pass  # placeholder"]:
            assert marker not in content, f"orchestrator.py still contains placeholder marker: {marker}"
