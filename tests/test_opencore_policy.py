"""Tests for opencore_policy.yaml validation."""

import pathlib

import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
POLICY_PATH = REPO_ROOT / "opencore_policy.yaml"

CANONICAL_ROOTS = [
    "03_core",
    "12_tooling",
    "16_codex",
    "23_compliance",
    "24_meta_orchestration",
]


@pytest.fixture(scope="module")
def policy():
    """Load the opencore policy YAML."""
    assert POLICY_PATH.exists(), f"Policy file not found: {POLICY_PATH}"
    with open(POLICY_PATH, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


class TestPolicyStructure:
    """Verify policy file has all required top-level keys."""

    REQUIRED_KEYS = [
        "version",
        "schema",
        "allowed_roots",
        "blocked_extensions",
        "sanitization_rules",
        "export_constraints",
        "enforcement",
    ]

    def test_required_keys_present(self, policy):
        for key in self.REQUIRED_KEYS:
            assert key in policy, f"Missing required key: {key}"

    def test_version_is_string(self, policy):
        assert isinstance(policy["version"], str)


class TestAllowedRoots:
    """Verify allowed_roots matches canonical open-core set."""

    def test_allowed_roots_match_canonical(self, policy):
        assert sorted(policy["allowed_roots"]) == sorted(CANONICAL_ROOTS)

    def test_no_extra_roots(self, policy):
        extras = set(policy["allowed_roots"]) - set(CANONICAL_ROOTS)
        assert not extras, f"Unexpected roots in policy: {extras}"

    def test_no_missing_roots(self, policy):
        missing = set(CANONICAL_ROOTS) - set(policy["allowed_roots"])
        assert not missing, f"Missing roots in policy: {missing}"


class TestBlockedExtensions:
    """Verify blocked extensions include dangerous file types."""

    MUST_BLOCK = [".env", ".pem", ".key", ".secret"]

    def test_dangerous_extensions_blocked(self, policy):
        blocked = policy["blocked_extensions"]
        for ext in self.MUST_BLOCK:
            assert ext in blocked, f"Extension {ext} must be blocked"

    def test_extensions_are_dotted(self, policy):
        for ext in policy["blocked_extensions"]:
            assert ext.startswith("."), f"Extension must start with dot: {ext}"


class TestSanitizationRules:
    """Verify sanitization rules enforce PII protection."""

    def test_strip_pii_enabled(self, policy):
        assert policy["sanitization_rules"]["strip_pii"] is True

    def test_hash_algorithm_is_sha3(self, policy):
        assert policy["sanitization_rules"]["hash_algorithm"] == "SHA3-256"

    def test_agent_prompts_removed(self, policy):
        assert policy["sanitization_rules"]["remove_agent_prompts"] is True


class TestEnforcement:
    """Verify enforcement mode is strict."""

    def test_strict_mode(self, policy):
        assert policy["enforcement"]["mode"] == "strict"

    def test_fail_on_violation(self, policy):
        assert policy["enforcement"]["fail_on_violation"] is True
