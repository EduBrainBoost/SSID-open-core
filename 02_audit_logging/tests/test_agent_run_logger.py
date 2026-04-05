"""Tests for AgentRunLogger.

Covers:
  - log_run_start returns a valid run_id and creates agent log
  - log_run_step appends step records
  - log_run_complete seals the run and updates the index
  - log_run_error records failure and removes from active set
  - hash chain integrity across multiple runs
  - ID validation rejects malformed agent_ids
"""

from __future__ import annotations

import json

# Add parent to path for import without package install
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "agent_runs"))

from agent_run_logger import _GENESIS_HASH, AgentRunLogger, _sha256


@pytest.fixture()
def logger(tmp_path: Path) -> AgentRunLogger:
    return AgentRunLogger(base_dir=tmp_path / "agent_runs")


class TestLogRunStart:
    def test_returns_run_id_string(self, logger: AgentRunLogger) -> None:
        run_id = logger.log_run_start("agent-a", task="do something", config={})
        assert isinstance(run_id, str)
        assert run_id.startswith("run-")

    def test_creates_agent_log_file(self, logger: AgentRunLogger, tmp_path: Path) -> None:
        logger.log_run_start("agent-b", task="task", config={})
        log_path = tmp_path / "agent_runs" / "runs" / "agent-b.jsonl"
        assert log_path.exists()

    def test_log_entry_has_expected_fields(self, logger: AgentRunLogger) -> None:
        run_id = logger.log_run_start("agent-c", task="test task", config={"k": "v"})
        entries = logger.read_agent_log("agent-c")
        assert len(entries) == 1
        entry = entries[0]
        assert entry["run_id"] == run_id
        assert entry["agent_id"] == "agent-c"
        assert entry["status"] == "started"
        assert "task_hash" in entry
        assert "config_hash" in entry
        assert "entry_hash" in entry
        assert "previous_entry_hash" in entry

    def test_task_stored_as_hash_not_raw(self, logger: AgentRunLogger) -> None:
        task = "sensitive task description"
        logger.log_run_start("agent-d", task=task, config={})
        entries = logger.read_agent_log("agent-d")
        entry_text = json.dumps(entries[0])
        assert task not in entry_text
        assert _sha256(task) in entry_text

    def test_invalid_agent_id_raises(self, logger: AgentRunLogger) -> None:
        with pytest.raises(ValueError):
            logger.log_run_start("../bad-id", task="x", config={})

    def test_invalid_agent_id_path_traversal(self, logger: AgentRunLogger) -> None:
        with pytest.raises(ValueError):
            logger.log_run_start("../../etc/passwd", task="x", config={})

    def test_run_appears_in_active(self, logger: AgentRunLogger) -> None:
        run_id = logger.log_run_start("agent-e", task="t", config={})
        record = logger.get_run_record(run_id)
        assert record is not None
        assert record.run_id == run_id


class TestLogRunStep:
    def test_step_appended_to_agent_log(self, logger: AgentRunLogger) -> None:
        run_id = logger.log_run_start("agent-s", task="t", config={})
        logger.log_run_step(
            run_id,
            step_name="write_file",
            input_hash="sha256:" + "a" * 64,
            output_hash="sha256:" + "b" * 64,
            status="ok",
        )
        entries = logger.read_agent_log("agent-s")
        step_entries = [e for e in entries if e.get("event") == "step"]
        assert len(step_entries) == 1
        assert step_entries[0]["step"]["step_name"] == "write_file"
        assert step_entries[0]["step"]["status"] == "ok"

    def test_step_has_step_hash(self, logger: AgentRunLogger) -> None:
        run_id = logger.log_run_start("agent-s2", task="t", config={})
        logger.log_run_step(run_id, "parse", "sha256:" + "c" * 64, "sha256:" + "d" * 64, "ok")
        entries = logger.read_agent_log("agent-s2")
        step_entry = [e for e in entries if e.get("event") == "step"][0]
        assert "step_hash" in step_entry["step"]

    def test_multiple_steps_recorded(self, logger: AgentRunLogger) -> None:
        run_id = logger.log_run_start("agent-s3", task="t", config={})
        for i in range(3):
            logger.log_run_step(run_id, f"step-{i}", "sha256:" + str(i) * 64, "sha256:" + "f" * 64, "ok")
        entries = logger.read_agent_log("agent-s3")
        step_entries = [e for e in entries if e.get("event") == "step"]
        assert len(step_entries) == 3

    def test_invalid_run_id_raises(self, logger: AgentRunLogger) -> None:
        with pytest.raises(KeyError):
            logger.log_run_step("nonexistent-run", "step", "sha256:" + "a" * 64, "sha256:" + "b" * 64, "ok")


class TestLogRunComplete:
    def test_completes_and_removes_from_active(self, logger: AgentRunLogger) -> None:
        run_id = logger.log_run_start("agent-cp", task="t", config={})
        logger.log_run_complete(run_id, result="success", evidence_hash="sha256:" + "e" * 64)
        assert logger.get_run_record(run_id) is None

    def test_complete_entry_in_log(self, logger: AgentRunLogger) -> None:
        run_id = logger.log_run_start("agent-cp2", task="t", config={})
        logger.log_run_complete(run_id, result="success", evidence_hash="sha256:" + "e" * 64)
        entries = logger.read_agent_log("agent-cp2")
        complete_entries = [e for e in entries if e.get("event") == "run_complete"]
        assert len(complete_entries) == 1
        assert complete_entries[0]["result"] == "success"

    def test_index_updated_on_complete(self, logger: AgentRunLogger, tmp_path: Path) -> None:
        run_id = logger.log_run_start("agent-cp3", task="t", config={})
        logger.log_run_complete(run_id, result="ok", evidence_hash="sha256:" + "f" * 64)
        index_path = tmp_path / "agent_runs" / "index.jsonl"
        assert index_path.exists()
        lines = [json.loads(l) for l in index_path.read_text().splitlines() if l.strip()]
        complete_lines = [l for l in lines if l.get("event") == "run_complete"]
        assert any(l["run_id"] == run_id for l in complete_lines)

    def test_hash_chain_updated_on_complete(self, logger: AgentRunLogger, tmp_path: Path) -> None:
        run_id = logger.log_run_start("agent-cp4", task="t", config={})
        logger.log_run_complete(run_id, result="ok", evidence_hash="sha256:" + "a" * 64)
        chain_path = tmp_path / "agent_runs" / "hash_chain.json"
        assert chain_path.exists()
        chain = json.loads(chain_path.read_text())
        assert len(chain) == 1
        assert chain[0]["run_id"] == run_id


class TestLogRunError:
    def test_error_removes_from_active(self, logger: AgentRunLogger) -> None:
        run_id = logger.log_run_start("agent-err", task="t", config={})
        logger.log_run_error(run_id, error="TIMEOUT", context={"attempt": 1})
        assert logger.get_run_record(run_id) is None

    def test_error_entry_in_log(self, logger: AgentRunLogger) -> None:
        run_id = logger.log_run_start("agent-err2", task="t", config={})
        logger.log_run_error(run_id, error="IO_ERROR")
        entries = logger.read_agent_log("agent-err2")
        err_entries = [e for e in entries if e.get("event") == "run_error"]
        assert len(err_entries) == 1
        assert err_entries[0]["error_code"] == "IO_ERROR"

    def test_context_stored_as_hash(self, logger: AgentRunLogger) -> None:
        run_id = logger.log_run_start("agent-err3", task="t", config={})
        ctx = {"file": "test.py", "line": 42}
        logger.log_run_error(run_id, error="PARSE_ERROR", context=ctx)
        entries = logger.read_agent_log("agent-err3")
        err_entry = [e for e in entries if e.get("event") == "run_error"][0]
        entry_text = json.dumps(err_entry)
        # context dict should not appear raw
        assert "test.py" not in entry_text
        assert "context_hash" in entry_text


class TestHashChain:
    def test_chain_valid_after_multiple_runs(self, logger: AgentRunLogger) -> None:
        for i in range(3):
            run_id = logger.log_run_start(f"chain-agent-{i}", task=f"task {i}", config={})
            logger.log_run_complete(run_id, result="ok", evidence_hash="sha256:" + str(i) * 64)

        result = logger.verify_chain()
        assert result["valid"] is True
        assert result["length"] == 3
        assert result["errors"] == []

    def test_chain_invalid_if_tampered(self, logger: AgentRunLogger, tmp_path: Path) -> None:
        run_id = logger.log_run_start("tamper-agent", task="t", config={})
        logger.log_run_complete(run_id, result="ok", evidence_hash="sha256:" + "a" * 64)

        chain_path = tmp_path / "agent_runs" / "hash_chain.json"
        chain = json.loads(chain_path.read_text())
        chain[0]["entry_hash"] = "sha256:" + "0" * 64  # tamper
        chain_path.write_text(json.dumps(chain))

        result = logger.verify_chain()
        assert result["valid"] is False

    def test_first_entry_previous_is_genesis(self, logger: AgentRunLogger, tmp_path: Path) -> None:
        run_id = logger.log_run_start("genesis-agent", task="t", config={})
        logger.log_run_complete(run_id, result="ok", evidence_hash="sha256:" + "b" * 64)
        chain_path = tmp_path / "agent_runs" / "hash_chain.json"
        chain = json.loads(chain_path.read_text())
        assert chain[0]["previous_chain_hash"] == _GENESIS_HASH
