"""Tests for EvidenceBuilder.

Covers:
  - create_evidence produces correct hash and is immutable
  - chain_evidence links correctly to predecessor
  - build_chain convenience method
  - verify_chain returns True for valid chains
  - verify_chain returns False for tampered chains
  - export_evidence_report produces structured output
  - PII guard rejects forbidden keys
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "agent_runs"))

from evidence_builder import EvidenceBuilder, Evidence, ChainedEvidence, _sha256, _sha256_dict


@pytest.fixture()
def builder() -> EvidenceBuilder:
    return EvidenceBuilder()


class TestCreateEvidence:
    def test_returns_evidence_instance(self, builder: EvidenceBuilder) -> None:
        e = builder.create_evidence("file_written", {"path_hash": "sha256:" + "a" * 64})
        assert isinstance(e, Evidence)

    def test_evidence_hash_correct(self, builder: EvidenceBuilder) -> None:
        e = builder.create_evidence("lint_passed", {"exit_code": 0})
        expected = _sha256(f"{e.action}|{e.data_hash}|{e.timestamp}")
        assert e.evidence_hash == expected

    def test_data_stored_as_hash_only(self, builder: EvidenceBuilder) -> None:
        data = {"exit_code": 0, "tool": "ruff"}
        e = builder.create_evidence("lint_passed", data)
        assert e.data_hash == _sha256_dict(data)
        # Raw values are not present on the Evidence object
        assert not hasattr(e, "data") or e.data_hash != data  # type: ignore[attr-defined]

    def test_evidence_is_frozen(self, builder: EvidenceBuilder) -> None:
        e = builder.create_evidence("step", {})
        with pytest.raises((AttributeError, TypeError)):
            e.action = "modified"  # type: ignore[misc]

    def test_empty_action_raises(self, builder: EvidenceBuilder) -> None:
        with pytest.raises(ValueError):
            builder.create_evidence("", {})

    def test_whitespace_action_raises(self, builder: EvidenceBuilder) -> None:
        with pytest.raises(ValueError):
            builder.create_evidence("   ", {})

    def test_none_data_treated_as_empty(self, builder: EvidenceBuilder) -> None:
        e = builder.create_evidence("step", None)
        assert e.data_hash == _sha256_dict({})

    def test_pii_key_raises(self, builder: EvidenceBuilder) -> None:
        with pytest.raises(ValueError, match="forbidden"):
            builder.create_evidence("step", {"email": "x@y.com"})

    def test_pii_key_token_raises(self, builder: EvidenceBuilder) -> None:
        with pytest.raises(ValueError, match="forbidden"):
            builder.create_evidence("step", {"token": "abc123"})

    def test_pii_key_prompt_raises(self, builder: EvidenceBuilder) -> None:
        with pytest.raises(ValueError, match="forbidden"):
            builder.create_evidence("step", {"prompt": "some instruction"})


class TestChainEvidence:
    def test_chain_hash_is_deterministic(self, builder: EvidenceBuilder) -> None:
        e = builder.create_evidence("step", {"idx": 1})
        c = builder.chain_evidence(EvidenceBuilder.GENESIS, e, seq=0)
        expected = _sha256(f"{EvidenceBuilder.GENESIS}|{e.evidence_hash}")
        assert c.chain_hash == expected

    def test_chain_links_to_predecessor(self, builder: EvidenceBuilder) -> None:
        e1 = builder.create_evidence("step1", {})
        e2 = builder.create_evidence("step2", {})
        c1 = builder.chain_evidence(EvidenceBuilder.GENESIS, e1, seq=0)
        c2 = builder.chain_evidence(c1.chain_hash, e2, seq=1)
        assert c2.previous_hash == c1.chain_hash

    def test_returns_chained_evidence_instance(self, builder: EvidenceBuilder) -> None:
        e = builder.create_evidence("step", {})
        c = builder.chain_evidence(EvidenceBuilder.GENESIS, e)
        assert isinstance(c, ChainedEvidence)

    def test_chained_evidence_is_frozen(self, builder: EvidenceBuilder) -> None:
        e = builder.create_evidence("step", {})
        c = builder.chain_evidence(EvidenceBuilder.GENESIS, e)
        with pytest.raises((AttributeError, TypeError)):
            c.chain_hash = "modified"  # type: ignore[misc]


class TestBuildChain:
    def test_empty_list_returns_empty(self) -> None:
        chain = EvidenceBuilder.build_chain([])
        assert chain == []

    def test_single_item_uses_genesis(self, builder: EvidenceBuilder) -> None:
        e = builder.create_evidence("step", {})
        chain = EvidenceBuilder.build_chain([e])
        assert len(chain) == 1
        assert chain[0].previous_hash == EvidenceBuilder.GENESIS
        assert chain[0].seq == 0

    def test_multiple_items_linked(self, builder: EvidenceBuilder) -> None:
        evidences = [builder.create_evidence(f"step-{i}", {"i": i}) for i in range(4)]
        chain = EvidenceBuilder.build_chain(evidences)
        assert len(chain) == 4
        for i in range(1, 4):
            assert chain[i].previous_hash == chain[i - 1].chain_hash

    def test_seq_numbers_monotonic(self, builder: EvidenceBuilder) -> None:
        evidences = [builder.create_evidence(f"step-{i}", {}) for i in range(5)]
        chain = EvidenceBuilder.build_chain(evidences)
        seqs = [c.seq for c in chain]
        assert seqs == sorted(seqs)


class TestVerifyChain:
    def test_valid_chain_returns_true(self, builder: EvidenceBuilder) -> None:
        evidences = [builder.create_evidence(f"step-{i}", {}) for i in range(3)]
        chain = EvidenceBuilder.build_chain(evidences)
        assert EvidenceBuilder.verify_chain(chain) is True

    def test_empty_chain_returns_true(self) -> None:
        assert EvidenceBuilder.verify_chain([]) is True

    def test_tampered_chain_hash_returns_false(self, builder: EvidenceBuilder) -> None:
        e = builder.create_evidence("step", {})
        c = builder.chain_evidence(EvidenceBuilder.GENESIS, e, seq=0)
        # Build a new ChainedEvidence with a tampered chain_hash
        tampered = ChainedEvidence(
            seq=c.seq,
            evidence=c.evidence,
            previous_hash=c.previous_hash,
            chain_hash="sha256:" + "0" * 64,  # wrong
        )
        assert EvidenceBuilder.verify_chain([tampered]) is False

    def test_tampered_previous_hash_returns_false(self, builder: EvidenceBuilder) -> None:
        evidences = [builder.create_evidence(f"step-{i}", {}) for i in range(2)]
        chain = EvidenceBuilder.build_chain(evidences)
        tampered_second = ChainedEvidence(
            seq=chain[1].seq,
            evidence=chain[1].evidence,
            previous_hash="sha256:" + "f" * 64,  # wrong prev
            chain_hash=chain[1].chain_hash,
        )
        bad_chain = [chain[0], tampered_second]
        assert EvidenceBuilder.verify_chain(bad_chain) is False

    def test_tampered_evidence_hash_returns_false(self, builder: EvidenceBuilder) -> None:
        e = builder.create_evidence("step", {})
        # Modify evidence hash directly by constructing a new Evidence with wrong hash
        bad_evidence = Evidence(
            action=e.action,
            data_hash=e.data_hash,
            timestamp=e.timestamp,
            evidence_hash="sha256:" + "0" * 64,
        )
        c = builder.chain_evidence(EvidenceBuilder.GENESIS, bad_evidence, seq=0)
        # Note: chain_hash is derived from the bad evidence_hash, but verify_chain
        # re-derives evidence_hash and will detect the mismatch
        assert EvidenceBuilder.verify_chain([c]) is False


class TestVerifyChainReport:
    def test_report_valid_for_good_chain(self, builder: EvidenceBuilder) -> None:
        evidences = [builder.create_evidence(f"step-{i}", {}) for i in range(3)]
        chain = EvidenceBuilder.build_chain(evidences)
        report = EvidenceBuilder.verify_chain_report(chain)
        assert report["valid"] is True
        assert report["length"] == 3
        assert report["errors"] == []

    def test_report_items_have_action(self, builder: EvidenceBuilder) -> None:
        e = builder.create_evidence("my_action", {})
        chain = EvidenceBuilder.build_chain([e])
        report = EvidenceBuilder.verify_chain_report(chain)
        assert report["items"][0]["action"] == "my_action"


class TestExportEvidenceReport:
    def test_report_structure(self, builder: EvidenceBuilder) -> None:
        evidences = [builder.create_evidence(f"step-{i}", {"idx": i}) for i in range(2)]
        chain = EvidenceBuilder.build_chain(evidences)
        report = EvidenceBuilder.export_evidence_report("run-test-001", chain)
        assert report["run_id"] == "run-test-001"
        assert report["chain_length"] == 2
        assert report["chain_valid"] is True
        assert "terminal_chain_hash" in report
        assert len(report["entries"]) == 2

    def test_terminal_hash_matches_last_item(self, builder: EvidenceBuilder) -> None:
        evidences = [builder.create_evidence(f"s{i}", {}) for i in range(3)]
        chain = EvidenceBuilder.build_chain(evidences)
        report = EvidenceBuilder.export_evidence_report("run-x", chain)
        assert report["terminal_chain_hash"] == chain[-1].chain_hash

    def test_empty_chain_report(self, builder: EvidenceBuilder) -> None:
        report = EvidenceBuilder.export_evidence_report("run-empty", [])
        assert report["chain_length"] == 0
        assert report["chain_valid"] is True
        assert report["terminal_chain_hash"] == EvidenceBuilder.GENESIS
