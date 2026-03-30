#!/usr/bin/env python3
"""Golden regression tests for the SoT convergence engine (PR-9).

Tests feed known fixture inputs through the convergence policy engine
and compare outputs byte-for-byte against golden expected outputs.

All external dependencies (scanner, manifest gen, opencore sync, git, filesystem)
are mocked. The convergence/derivation policy evaluation is tested directly.

No scores -- PASS/FAIL + findings only.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

from cli.run_sot_convergence import (
    EXIT_DENY,
    EXIT_SUCCESS,
    EXIT_WARN,
    _collect,
    _decide,
    _max_sev,
    _step_policy,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "golden"
EXPECTED_DIR = FIXTURES_DIR / "expected"

FIXTURE_NAMES = [
    "canonical_clean",
    "derivative_leakage",
    "contract_hash_mismatch",
    "missing_expected_artifact",
    "warn_info_only",
    "multi_finding_ordering",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_fixture(name: str) -> Dict[str, Any]:
    """Load a golden fixture JSON file by name."""
    path = FIXTURES_DIR / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _load_expected(name: str) -> Dict[str, Any]:
    """Load expected output JSON for a golden fixture."""
    path = EXPECTED_DIR / f"{name}.expected.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _run_engine(fixture: Dict[str, Any]) -> Dict[str, Any]:
    """Run the convergence engine on a fixture and return a deterministic report.

    Uses fixed timestamps and UUIDs to ensure byte-stable output.
    """
    scan = fixture["scan"]
    sync = fixture["sync"]

    # Run policy evaluation directly -- volatile fields (timestamp, evidence_hash)
    # are stripped before comparison, so no datetime patching needed.
    policy_findings = _step_policy(scan, sync)

    findings = _collect(scan, sync, policy_findings)
    decision, exit_code = _decide(findings)

    # Sort findings deterministically for stable output
    findings_sorted = sorted(
        findings,
        key=lambda f: (f.get("source", ""), f.get("id", ""), f.get("class", ""),
                        f.get("severity", ""), f.get("path", "")),
    )

    # Build severity counts
    severity_counts: Dict[str, int] = {}
    for f in findings_sorted:
        sev = f.get("severity", "info")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    # Build class counts
    class_counts: Dict[str, int] = {}
    for f in findings_sorted:
        cls = f.get("class", "unknown")
        class_counts[cls] = class_counts.get(cls, 0) + 1

    # Build deterministic output (no timestamps, no UUIDs, no git hashes)
    output = {
        "fixture_name": fixture.get("description", ""),
        "decision": decision,
        "exit_code": exit_code,
        "exit_label": {EXIT_SUCCESS: "success", EXIT_WARN: "warn",
                       EXIT_DENY: "deny"}.get(exit_code, "unknown"),
        "total_findings": len(findings_sorted),
        "max_severity": _max_sev(findings_sorted),
        "severity_counts": severity_counts,
        "class_counts": class_counts,
        "findings": _strip_volatile_fields(findings_sorted),
    }
    return output


def _strip_volatile_fields(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove timestamp and evidence_hash fields that vary between runs.

    Keeps all structural/content fields for regression comparison.
    """
    stable = []
    for f in findings:
        entry = {
            "id": f.get("id", ""),
            "class": f.get("class", ""),
            "severity": f.get("severity", ""),
            "source": f.get("source", ""),
            "path": f.get("path", ""),
            "details": f.get("details", ""),
            "repo": f.get("repo", ""),
        }
        stable.append(entry)
    return stable


def _canonical_json(data: Any) -> str:
    """Produce canonical JSON string for byte-stable comparison."""
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Fixture loading tests
# ---------------------------------------------------------------------------

class TestFixtureIntegrity:
    """Verify fixture files are well-formed and contain required fields."""

    @pytest.mark.parametrize("name", FIXTURE_NAMES)
    def test_fixture_loadable(self, name: str):
        """Each fixture file must be valid JSON with required keys."""
        fixture = _load_fixture(name)
        assert "scan" in fixture, f"Fixture {name} missing 'scan'"
        assert "sync" in fixture, f"Fixture {name} missing 'sync'"
        assert "expected" in fixture, f"Fixture {name} missing 'expected'"
        assert "description" in fixture, f"Fixture {name} missing 'description'"

    @pytest.mark.parametrize("name", FIXTURE_NAMES)
    def test_expected_output_loadable(self, name: str):
        """Each expected output file must be valid JSON."""
        expected = _load_expected(name)
        assert "decision" in expected
        assert "exit_code" in expected
        assert "total_findings" in expected
        assert "findings" in expected


# ---------------------------------------------------------------------------
# Golden regression tests
# ---------------------------------------------------------------------------

class TestGoldenRegression:
    """Compare engine output against golden expected outputs byte-for-byte."""

    @pytest.mark.parametrize("name", FIXTURE_NAMES)
    def test_golden_output_matches(self, name: str):
        """Engine output must match golden expected output exactly."""
        fixture = _load_fixture(name)
        expected = _load_expected(name)
        actual = _run_engine(fixture)

        actual_json = _canonical_json(actual)
        expected_json = _canonical_json(expected)

        assert actual_json == expected_json, (
            f"Golden regression mismatch for '{name}'.\n"
            f"--- Expected ---\n{expected_json[:2000]}\n"
            f"--- Actual ---\n{actual_json[:2000]}"
        )

    def test_canonical_clean_golden(self):
        """Clean pass fixture: info-only findings, decision=pass, exit=0."""
        fixture = _load_fixture("canonical_clean")
        result = _run_engine(fixture)
        expected = _load_expected("canonical_clean")

        assert result["decision"] == "pass"
        assert result["exit_code"] == EXIT_SUCCESS
        # Engine emits I-002 (full export) and I-004 (derivation mode) info findings
        assert result["total_findings"] == 2
        assert all(f["severity"] == "info" for f in result["findings"])
        assert _canonical_json(result) == _canonical_json(expected)

    def test_derivative_leakage_golden(self):
        """Forbidden export: decision=fail, exit=DENY, critical findings."""
        fixture = _load_fixture("derivative_leakage")
        result = _run_engine(fixture)
        expected = _load_expected("derivative_leakage")

        assert result["decision"] == "fail"
        assert result["exit_code"] == EXIT_DENY
        assert any(f["class"] == "policy_deny" for f in result["findings"])
        assert any("forbidden" in f["details"].lower() for f in result["findings"]
                    if f["class"] == "policy_deny")
        assert _canonical_json(result) == _canonical_json(expected)

    def test_contract_hash_mismatch_golden(self):
        """Contract hash mismatch: decision=fail, exit=DENY."""
        fixture = _load_fixture("contract_hash_mismatch")
        result = _run_engine(fixture)
        expected = _load_expected("contract_hash_mismatch")

        assert result["decision"] == "fail"
        assert result["exit_code"] == EXIT_DENY
        assert any("contract_hash_mismatch" in f["details"]
                    for f in result["findings"] if f["class"] == "policy_deny")
        assert _canonical_json(result) == _canonical_json(expected)

    def test_missing_artifact_golden(self):
        """Missing artifact in canonical: decision=fail, exit=DENY."""
        fixture = _load_fixture("missing_expected_artifact")
        result = _run_engine(fixture)
        expected = _load_expected("missing_expected_artifact")

        assert result["decision"] == "fail"
        assert result["exit_code"] == EXIT_DENY
        assert result["total_findings"] >= 1
        assert _canonical_json(result) == _canonical_json(expected)

    def test_warn_info_only_golden(self):
        """Warn/info only: decision=warn, exit=WARN, no critical."""
        fixture = _load_fixture("warn_info_only")
        result = _run_engine(fixture)
        expected = _load_expected("warn_info_only")

        assert result["decision"] == "warn"
        assert result["exit_code"] == EXIT_WARN
        assert result["severity_counts"].get("critical", 0) == 0
        assert not any(f["class"] == "policy_deny" for f in result["findings"])
        assert _canonical_json(result) == _canonical_json(expected)

    def test_multi_finding_deterministic_ordering(self):
        """Multiple findings must always sort in the same deterministic order."""
        fixture = _load_fixture("multi_finding_ordering")
        expected = _load_expected("multi_finding_ordering")

        # Run 5 times and verify order is identical each time
        results = [_run_engine(copy.deepcopy(fixture)) for _ in range(5)]
        baseline = _canonical_json(results[0])
        for i, r in enumerate(results[1:], 1):
            assert _canonical_json(r) == baseline, (
                f"Ordering diverged on run {i+1}"
            )
        assert _canonical_json(results[0]) == _canonical_json(expected)


# ---------------------------------------------------------------------------
# Byte stability / determinism tests
# ---------------------------------------------------------------------------

class TestByteStability:
    """Verify that identical inputs always produce byte-identical outputs."""

    @pytest.mark.parametrize("name", FIXTURE_NAMES)
    def test_canonical_json_byte_stability(self, name: str):
        """Same fixture input must produce identical canonical JSON bytes every time."""
        fixture = _load_fixture(name)
        result_a = _run_engine(copy.deepcopy(fixture))
        result_b = _run_engine(copy.deepcopy(fixture))

        json_a = _canonical_json(result_a)
        json_b = _canonical_json(result_b)

        assert json_a == json_b, (
            f"Byte stability violation for '{name}': outputs differ across runs"
        )

    @pytest.mark.parametrize("name", FIXTURE_NAMES)
    def test_hash_stability(self, name: str):
        """SHA-256 hash of canonical output must be stable across runs."""
        fixture = _load_fixture(name)
        result_a = _run_engine(copy.deepcopy(fixture))
        result_b = _run_engine(copy.deepcopy(fixture))

        hash_a = hashlib.sha256(_canonical_json(result_a).encode("utf-8")).hexdigest()
        hash_b = hashlib.sha256(_canonical_json(result_b).encode("utf-8")).hexdigest()

        assert hash_a == hash_b, (
            f"Hash stability violation for '{name}': {hash_a} != {hash_b}"
        )

    @pytest.mark.parametrize("name", FIXTURE_NAMES)
    def test_sort_order_stability(self, name: str):
        """Finding sort order must be deterministic regardless of internal ordering."""
        fixture = _load_fixture(name)

        # Run multiple times with deepcopy to ensure no state leakage
        runs = [_run_engine(copy.deepcopy(fixture)) for _ in range(3)]

        if runs[0]["total_findings"] > 0:
            baseline_ids = [f["id"] for f in runs[0]["findings"]]
            for i, r in enumerate(runs[1:], 1):
                run_ids = [f["id"] for f in r["findings"]]
                assert run_ids == baseline_ids, (
                    f"Sort order diverged on run {i+1} for '{name}'"
                )


# ---------------------------------------------------------------------------
# Determinism proof
# ---------------------------------------------------------------------------

class TestDeterminismProof:
    """Run each fixture twice and assert byte-identical output as proof of determinism."""

    @pytest.mark.parametrize("name", FIXTURE_NAMES)
    def test_determinism_proof_double_run(self, name: str):
        """Determinism proof: two runs with identical input produce identical output."""
        fixture = _load_fixture(name)

        output_1 = _run_engine(copy.deepcopy(fixture))
        output_2 = _run_engine(copy.deepcopy(fixture))

        bytes_1 = _canonical_json(output_1).encode("utf-8")
        bytes_2 = _canonical_json(output_2).encode("utf-8")

        assert bytes_1 == bytes_2, (
            f"Determinism proof FAILED for '{name}': "
            f"outputs are not byte-identical across runs"
        )

        # Also verify SHA-256 match as secondary proof
        sha_1 = hashlib.sha256(bytes_1).hexdigest()
        sha_2 = hashlib.sha256(bytes_2).hexdigest()
        assert sha_1 == sha_2


# ---------------------------------------------------------------------------
# Expected output generator (run with --update-golden flag or standalone)
# ---------------------------------------------------------------------------

def generate_expected_outputs():
    """Generate/update all expected output files from current engine behavior.

    Run this function to (re-)baseline the golden expected outputs:
        python -c "from tests.test_golden_regression import generate_expected_outputs; generate_expected_outputs()"
    """
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)
    for name in FIXTURE_NAMES:
        fixture = _load_fixture(name)
        output = _run_engine(fixture)
        out_path = EXPECTED_DIR / f"{name}.expected.json"
        out_path.write_text(
            _canonical_json(output) + "\n", encoding="utf-8"
        )
        print(f"  Written: {out_path}")
    print(f"Generated {len(FIXTURE_NAMES)} expected output files.")


if __name__ == "__main__":
    generate_expected_outputs()
