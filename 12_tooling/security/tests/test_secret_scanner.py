#!/usr/bin/env python3
"""Tests for 12_tooling.security.secret_scanner — SecretScanner class.

Covers:
  - Pattern detection for all major secret categories
  - Inline suppression comment honouring
  - Allow-list: path-based and pattern-label-based suppression
  - scan_file() / scan_directory() public API
  - get_findings() accumulation across multiple calls
  - get_summary() correctness
  - Binary / large file skipping
  - reset() state clearing

SoT v4.1.0 | ROOT-24-LOCK
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Make parent 12_tooling importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from security.secret_scanner import (
    _SUPPRESS_COMMENT,
    ScanSummary,
    SecretFinding,
    SecretScanner,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def scanner() -> SecretScanner:
    return SecretScanner()


@pytest.fixture()
def clean_py(tmp_path: Path) -> Path:
    return _write(tmp_path / "clean.py", '"""No secrets here."""\nimport os\n')


@pytest.fixture()
def aws_key_py(tmp_path: Path) -> Path:
    return _write(
        tmp_path / "aws_key.py",
        'access_key = "AKIAIOSFODNN7EXAMPLE"\n',
    )


@pytest.fixture()
def github_token_py(tmp_path: Path) -> Path:
    return _write(
        tmp_path / "gh_token.py",
        'token = "ghp_' + "a" * 36 + '"\n',
    )


@pytest.fixture()
def private_key_pem(tmp_path: Path) -> Path:
    return _write(
        tmp_path / "key.pem",
        "-----BEGIN RSA PRIVATE KEY-----\nMIIEow...\n-----END RSA PRIVATE KEY-----\n",
    )


@pytest.fixture()
def allowlist_json(tmp_path: Path) -> Path:
    data = {
        "paths": [],
        "patterns": ["AWS_ACCESS_KEY_ID"],
    }
    p = tmp_path / "allowlist.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


# ===========================================================================
# Tests — Pattern detection
# ===========================================================================


class TestPatternDetection:
    def test_detect_aws_access_key(self, scanner: SecretScanner, aws_key_py: Path) -> None:
        findings = scanner.scan_file(aws_key_py)
        labels = [f.pattern_label for f in findings]
        assert "AWS_ACCESS_KEY_ID" in labels

    def test_detect_github_token(self, scanner: SecretScanner, github_token_py: Path) -> None:
        findings = scanner.scan_file(github_token_py)
        labels = [f.pattern_label for f in findings]
        assert "GITHUB_TOKEN_PAT" in labels

    def test_detect_private_key(self, scanner: SecretScanner, tmp_path: Path) -> None:
        f = _write(tmp_path / "privkey.py", '"""Contains PEM."""\nkey = "-----BEGIN RSA PRIVATE KEY-----"\n')
        findings = scanner.scan_file(f)
        assert any("PRIVATE_KEY" in ff.pattern_label for ff in findings)

    def test_detect_openai_key(self, scanner: SecretScanner, tmp_path: Path) -> None:
        f = _write(tmp_path / "openai.py", 'API_KEY = "sk-' + "a" * 48 + '"\n')
        findings = scanner.scan_file(f)
        labels = [ff.pattern_label for ff in findings]
        assert "OPENAI_API_KEY" in labels

    def test_detect_database_url(self, scanner: SecretScanner, tmp_path: Path) -> None:
        f = _write(tmp_path / "db.py", 'DB = "postgresql://user:pass@db.example.com/mydb"\n')
        findings = scanner.scan_file(f)
        assert any("DATABASE_URL" in ff.pattern_label for ff in findings)

    def test_detect_stripe_test_key(self, scanner: SecretScanner, tmp_path: Path) -> None:
        f = _write(tmp_path / "stripe.py", 'key = "sk_test_' + "a" * 24 + '"\n')
        findings = scanner.scan_file(f)
        labels = [ff.pattern_label for ff in findings]
        assert "STRIPE_TEST_KEY" in labels

    def test_detect_generic_password(self, scanner: SecretScanner, tmp_path: Path) -> None:
        f = _write(tmp_path / "config.py", 'password = "SuperS3cretP@ss!"\n')
        findings = scanner.scan_file(f)
        assert any("GENERIC_PASSWORD" in ff.pattern_label for ff in findings)

    def test_no_false_positive_on_clean_file(self, scanner: SecretScanner, clean_py: Path) -> None:
        findings = scanner.scan_file(clean_py)
        assert findings == []


# ===========================================================================
# Tests — Inline suppression
# ===========================================================================


class TestInlineSuppression:
    def test_suppression_comment_prevents_finding(self, scanner: SecretScanner, tmp_path: Path) -> None:
        f = _write(
            tmp_path / "suppressed.py",
            f'token = "AKIAIOSFODNN7EXAMPLE"  # {_SUPPRESS_COMMENT}\n',
        )
        findings = scanner.scan_file(f)
        assert findings == []

    def test_suppression_only_on_matching_line(self, scanner: SecretScanner, tmp_path: Path) -> None:
        content = f'token = "AKIAIOSFODNN7EXAMPLE"  # {_SUPPRESS_COMMENT}\nother_key = "AKIAIOSFODNN7EXAMPLE"\n'
        f = _write(tmp_path / "partial.py", content)
        findings = scanner.scan_file(f)
        # Line 1 suppressed, line 2 should still be detected
        assert len(findings) == 1
        assert findings[0].line_number == 2


# ===========================================================================
# Tests — Allow-list
# ===========================================================================


class TestAllowList:
    def test_pattern_label_allowlist_suppresses_finding(
        self, tmp_path: Path, aws_key_py: Path, allowlist_json: Path
    ) -> None:
        scanner = SecretScanner(allowlist_path=allowlist_json)
        findings = scanner.scan_file(aws_key_py)
        # AWS_ACCESS_KEY_ID is in allowlist.patterns → suppressed
        assert not any(f.pattern_label == "AWS_ACCESS_KEY_ID" for f in findings)

    def test_path_allowlist_suppresses_file(self, tmp_path: Path) -> None:
        fixtures_dir = tmp_path / "fixtures"
        fixtures_dir.mkdir(exist_ok=True)
        secret_file = fixtures_dir / "test_key.py"
        secret_file.write_text('k = "AKIAIOSFODNN7EXAMPLE"\n', encoding="utf-8")

        allowlist_data = {"paths": [str(secret_file)], "patterns": []}
        al_path = tmp_path / "al.json"
        al_path.write_text(json.dumps(allowlist_data), encoding="utf-8")

        scanner = SecretScanner(allowlist_path=al_path)
        findings = scanner.scan_file(secret_file)
        assert findings == []

    def test_inline_allowlist_entries(self, tmp_path: Path, aws_key_py: Path) -> None:
        scanner = SecretScanner(allowlist_entries={"AWS_ACCESS_KEY_ID"})
        findings = scanner.scan_file(aws_key_py)
        assert not any(f.pattern_label == "AWS_ACCESS_KEY_ID" for f in findings)


# ===========================================================================
# Tests — scan_directory
# ===========================================================================


class TestScanDirectory:
    def test_scan_directory_finds_secrets(self, scanner: SecretScanner, tmp_path: Path) -> None:
        _write(tmp_path / "a.py", 'k = "ghp_' + "a" * 36 + '"\n')
        _write(tmp_path / "b.py", '"""clean"""\n')
        scanner.scan_directory(tmp_path)
        labels = [f.pattern_label for f in scanner.get_findings()]
        assert "GITHUB_TOKEN_PAT" in labels

    def test_scan_directory_skips_binary_extension(self, scanner: SecretScanner, tmp_path: Path) -> None:
        # .pyc files should be skipped regardless of content
        pyc = tmp_path / "compiled.pyc"
        pyc.write_bytes(b"AKIAIOSFODNN7EXAMPLE")
        scanner.scan_directory(tmp_path)
        assert scanner.get_findings() == []

    def test_scan_directory_recurses(self, scanner: SecretScanner, tmp_path: Path) -> None:
        subdir = tmp_path / "sub" / "nested"
        subdir.mkdir(parents=True)
        _write(subdir / "deep.py", 'k = "AKIAIOSFODNN7EXAMPLE"\n')
        scanner.scan_directory(tmp_path)
        assert len(scanner.get_findings()) >= 1

    def test_scan_nonexistent_directory(self, scanner: SecretScanner, tmp_path: Path) -> None:
        results = scanner.scan_directory(tmp_path / "nonexistent")
        assert results == []
        assert len(scanner._errors) >= 1


# ===========================================================================
# Tests — get_findings() / get_summary() / reset()
# ===========================================================================


class TestScannerState:
    def test_get_findings_accumulates_across_calls(self, tmp_path: Path) -> None:
        scanner = SecretScanner()
        _write(tmp_path / "f1.py", 'k = "AKIAIOSFODNN7EXAMPLE"\n')
        _write(tmp_path / "f2.py", 't = "ghp_' + "a" * 36 + '"\n')
        scanner.scan_file(tmp_path / "f1.py")
        scanner.scan_file(tmp_path / "f2.py")
        findings = scanner.get_findings()
        assert len(findings) == 2

    def test_get_summary_counts_correctly(self, tmp_path: Path) -> None:
        scanner = SecretScanner()
        _write(tmp_path / "crit.py", 'k = "AKIAIOSFODNN7EXAMPLE"\n')
        scanner.scan_file(tmp_path / "crit.py")
        summary = scanner.get_summary(root_path=str(tmp_path))
        assert isinstance(summary, ScanSummary)
        assert summary.total_findings >= 1
        assert summary.critical >= 1
        assert summary.files_scanned >= 1

    def test_reset_clears_state(self, tmp_path: Path, aws_key_py: Path) -> None:
        scanner = SecretScanner()
        scanner.scan_file(aws_key_py)
        assert len(scanner.get_findings()) >= 1
        scanner.reset()
        assert scanner.get_findings() == []
        assert scanner._files_scanned == 0
        assert scanner._errors == []

    def test_finding_has_correct_fields(self, tmp_path: Path) -> None:
        f = _write(tmp_path / "f.py", 'k = "AKIAIOSFODNN7EXAMPLE"\n')
        scanner = SecretScanner()
        findings = scanner.scan_file(f)
        assert len(findings) >= 1
        finding = findings[0]
        assert isinstance(finding, SecretFinding)
        assert finding.line_number == 1
        assert finding.severity in ("critical", "high", "medium")
        assert len(finding.matched_text) <= 42  # 40 chars + ellipsis

    def test_severity_critical_for_aws_key(self, tmp_path: Path) -> None:
        f = _write(tmp_path / "aws.py", 'k = "AKIAIOSFODNN7EXAMPLE"\n')
        scanner = SecretScanner()
        findings = scanner.scan_file(f)
        aws_findings = [ff for ff in findings if ff.pattern_label == "AWS_ACCESS_KEY_ID"]
        assert all(ff.severity == "critical" for ff in aws_findings)
