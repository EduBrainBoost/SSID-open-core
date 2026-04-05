"""Tests for RegistryWriter.

Covers:
  - register_agent creates entry with hashed config
  - register_agent is idempotent
  - update_agent_status transitions and counters
  - get_agent_history returns correct run records
  - record_run appends correctly
  - export_registry produces complete structured output
  - persistence: reloads state from disk
  - event log is append-only JSONL
  - invalid status raises ValueError
  - unregistered agent raises KeyError
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "agent_runs"))

from registry_writer import RegistryEntry, RegistryWriter, RunRecord, _sha256_dict


@pytest.fixture()
def writer(tmp_path: Path) -> RegistryWriter:
    return RegistryWriter(base_dir=tmp_path / "registry")


class TestRegisterAgent:
    def test_returns_registry_entry(self, writer: RegistryWriter) -> None:
        entry = writer.register_agent("agent-x", config={"model": "sonnet"})
        assert isinstance(entry, RegistryEntry)
        assert entry.agent_id == "agent-x"

    def test_config_stored_as_hash(self, writer: RegistryWriter) -> None:
        config = {"model": "sonnet-4-6", "role": "auditor"}
        entry = writer.register_agent("agent-y", config=config)
        assert entry.config_hash == _sha256_dict(config)

    def test_initial_status_is_registered(self, writer: RegistryWriter) -> None:
        entry = writer.register_agent("agent-z")
        assert entry.status == "registered"

    def test_idempotent_same_config(self, writer: RegistryWriter) -> None:
        e1 = writer.register_agent("agent-idem", config={"v": 1})
        e2 = writer.register_agent("agent-idem", config={"v": 1})
        assert e1.agent_id == e2.agent_id
        assert e1.registered_at == e2.registered_at

    def test_empty_agent_id_raises(self, writer: RegistryWriter) -> None:
        with pytest.raises(ValueError):
            writer.register_agent("", config={})

    def test_registry_json_created(self, writer: RegistryWriter, tmp_path: Path) -> None:
        writer.register_agent("agent-file")
        registry_path = tmp_path / "registry" / "registry.json"
        assert registry_path.exists()

    def test_event_log_created(self, writer: RegistryWriter, tmp_path: Path) -> None:
        writer.register_agent("agent-events")
        events_path = tmp_path / "registry" / "registry_events.jsonl"
        assert events_path.exists()

    def test_event_log_has_registered_event(self, writer: RegistryWriter, tmp_path: Path) -> None:
        writer.register_agent("agent-ev2", config={})
        events_path = tmp_path / "registry" / "registry_events.jsonl"
        lines = [json.loads(l) for l in events_path.read_text().splitlines() if l.strip()]
        assert any(l["event"] == "registered" and l["agent_id"] == "agent-ev2" for l in lines)

    def test_config_change_updates_hash(self, writer: RegistryWriter) -> None:
        writer.register_agent("agent-cfg", config={"v": 1})
        entry = writer.register_agent("agent-cfg", config={"v": 2})
        assert entry.config_hash == _sha256_dict({"v": 2})


class TestUpdateAgentStatus:
    def test_status_updated(self, writer: RegistryWriter) -> None:
        writer.register_agent("agent-upd")
        writer.update_agent_status("agent-upd", "idle")
        data = json.loads((writer._registry_path).read_text())
        assert data["agents"]["agent-upd"]["status"] == "idle"

    def test_run_count_increments_on_running(self, writer: RegistryWriter) -> None:
        writer.register_agent("agent-cnt")
        writer.update_agent_status("agent-cnt", "running", run_id="run-001")
        writer.update_agent_status("agent-cnt", "completed", run_id="run-001")
        writer.update_agent_status("agent-cnt", "running", run_id="run-002")
        data = json.loads(writer._registry_path.read_text())
        assert data["agents"]["agent-cnt"]["run_count"] == 2

    def test_completed_count_increments(self, writer: RegistryWriter) -> None:
        writer.register_agent("agent-comp")
        writer.update_agent_status("agent-comp", "running", run_id="run-a")
        writer.update_agent_status("agent-comp", "completed", run_id="run-a")
        data = json.loads(writer._registry_path.read_text())
        assert data["agents"]["agent-comp"]["completed_count"] == 1

    def test_failed_count_increments(self, writer: RegistryWriter) -> None:
        writer.register_agent("agent-fail")
        writer.update_agent_status("agent-fail", "running", run_id="run-f")
        writer.update_agent_status("agent-fail", "failed", run_id="run-f")
        data = json.loads(writer._registry_path.read_text())
        assert data["agents"]["agent-fail"]["failed_count"] == 1

    def test_invalid_status_raises(self, writer: RegistryWriter) -> None:
        writer.register_agent("agent-inv")
        with pytest.raises(ValueError, match="Invalid status"):
            writer.update_agent_status("agent-inv", "unknown_status")

    def test_unregistered_agent_raises(self, writer: RegistryWriter) -> None:
        with pytest.raises(KeyError):
            writer.update_agent_status("ghost-agent", "idle")

    def test_last_run_id_updated(self, writer: RegistryWriter) -> None:
        writer.register_agent("agent-lrid")
        writer.update_agent_status("agent-lrid", "running", run_id="run-xyz")
        data = json.loads(writer._registry_path.read_text())
        assert data["agents"]["agent-lrid"]["last_run_id"] == "run-xyz"

    def test_evidence_hash_stored(self, writer: RegistryWriter) -> None:
        writer.register_agent("agent-evh")
        ev_hash = "sha256:" + "a" * 64
        writer.update_agent_status("agent-evh", "completed", evidence_hash=ev_hash)
        data = json.loads(writer._registry_path.read_text())
        assert data["agents"]["agent-evh"]["last_evidence_hash"] == ev_hash


class TestGetAgentHistory:
    def test_empty_history_on_new_agent(self, writer: RegistryWriter) -> None:
        writer.register_agent("agent-hist")
        history = writer.get_agent_history("agent-hist")
        assert history == []

    def test_history_grows_with_runs(self, writer: RegistryWriter) -> None:
        writer.register_agent("agent-hist2")
        writer.update_agent_status("agent-hist2", "running", run_id="r1")
        writer.update_agent_status("agent-hist2", "completed", run_id="r1")
        writer.update_agent_status("agent-hist2", "running", run_id="r2")
        writer.update_agent_status("agent-hist2", "completed", run_id="r2")
        history = writer.get_agent_history("agent-hist2")
        assert len(history) == 2

    def test_unregistered_agent_raises(self, writer: RegistryWriter) -> None:
        with pytest.raises(KeyError):
            writer.get_agent_history("ghost")

    def test_returns_copies_not_references(self, writer: RegistryWriter) -> None:
        writer.register_agent("agent-copy")
        h1 = writer.get_agent_history("agent-copy")
        h2 = writer.get_agent_history("agent-copy")
        assert h1 is not h2


class TestRecordRun:
    def test_record_appended(self, writer: RegistryWriter) -> None:
        writer.register_agent("agent-rec")
        r = writer.record_run(
            "agent-rec",
            run_id="run-direct",
            status="completed",
            evidence_hash="sha256:" + "b" * 64,
            result="success",
        )
        assert isinstance(r, RunRecord)
        history = writer.get_agent_history("agent-rec")
        assert len(history) == 1
        assert history[0].run_id == "run-direct"

    def test_unregistered_agent_raises(self, writer: RegistryWriter) -> None:
        with pytest.raises(KeyError):
            writer.record_run("ghost", run_id="run-x", status="completed")


class TestExportRegistry:
    def test_export_structure(self, writer: RegistryWriter) -> None:
        writer.register_agent("agent-exp1", config={"v": 1})
        writer.register_agent("agent-exp2", config={"v": 2})
        export = writer.export_registry()
        assert "generated_at" in export
        assert "agent_count" in export
        assert export["agent_count"] == 2
        assert "agents" in export
        assert "history" in export
        assert "registry_hash" in export

    def test_registry_hash_deterministic(self, writer: RegistryWriter) -> None:
        writer.register_agent("agent-hash1")
        h1 = writer.export_registry()["registry_hash"]
        h2 = writer.export_registry()["registry_hash"]
        assert h1 == h2

    def test_export_agents_sorted(self, writer: RegistryWriter) -> None:
        writer.register_agent("zzz-agent")
        writer.register_agent("aaa-agent")
        export = writer.export_registry()
        keys = list(export["agents"].keys())
        assert keys == sorted(keys)


class TestPersistence:
    def test_reload_from_disk(self, tmp_path: Path) -> None:
        base = tmp_path / "persist-reg"
        w1 = RegistryWriter(base_dir=base)
        w1.register_agent("persist-agent", config={"role": "tester"})
        w1.update_agent_status("persist-agent", "idle")

        # New instance reading from same dir
        w2 = RegistryWriter(base_dir=base)
        assert "persist-agent" in w2._agents
        assert w2._agents["persist-agent"].status == "idle"

    def test_history_persisted(self, tmp_path: Path) -> None:
        base = tmp_path / "persist-hist"
        w1 = RegistryWriter(base_dir=base)
        w1.register_agent("hist-agent")
        w1.record_run("hist-agent", run_id="run-p1", status="completed", result="ok")

        w2 = RegistryWriter(base_dir=base)
        history = w2.get_agent_history("hist-agent")
        assert len(history) == 1
        assert history[0].run_id == "run-p1"
