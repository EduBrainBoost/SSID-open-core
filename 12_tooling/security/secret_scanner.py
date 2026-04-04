#!/usr/bin/env python3
"""SSID Secret Scanner.

Scans source files and directories for leaked secrets such as API keys,
tokens, passwords, and private keys.

Detection uses a curated set of regex patterns covering common secret
formats.  False-positive suppression is handled via a configurable
allow-list of file paths, line-level inline suppressions, and an optional
path-pattern ignore list.

Usage:
    python 12_tooling/security/secret_scanner.py --path .
    python 12_tooling/security/secret_scanner.py --path 03_core --output report.json
    python 12_tooling/security/secret_scanner.py --path . --allowlist allowlist.json

SoT v4.1.0 | ROOT-24-LOCK
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Secret pattern registry
# ---------------------------------------------------------------------------

#: Each entry is (label, compiled_regex).  Patterns are intentionally
#: conservative (low false-negative rate) while accepting that a small
#: number of test fixtures may need to be added to the allow-list.
_SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # AWS credentials
    ("AWS_ACCESS_KEY_ID", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    (
        "AWS_SECRET_ACCESS_KEY",
        re.compile(r"(?i)aws[_\-]?secret[_\-]?access[_\-]?key\s*[=:]\s*['\"]?[A-Za-z0-9/+]{40}['\"]?"),
    ),
    # GitHub tokens
    ("GITHUB_TOKEN_PAT", re.compile(r"\bghp_[a-zA-Z0-9]{36}\b")),
    ("GITHUB_TOKEN_OAUTH", re.compile(r"\bgho_[a-zA-Z0-9]{36}\b")),
    ("GITHUB_TOKEN_APP", re.compile(r"\bghu_[a-zA-Z0-9]{36}\b")),
    ("GITHUB_TOKEN_REFRESH", re.compile(r"\bghr_[a-zA-Z0-9]{76}\b")),
    # OpenAI / Anthropic
    ("OPENAI_API_KEY", re.compile(r"\bsk-[a-zA-Z0-9]{48}\b")),
    ("ANTHROPIC_API_KEY", re.compile(r"\bsk-ant-[a-zA-Z0-9\-_]{32,}\b")),
    # Slack tokens
    ("SLACK_BOT_TOKEN", re.compile(r"\bxoxb-[0-9]+-[0-9]+-[a-zA-Z0-9]+")),
    ("SLACK_APP_TOKEN", re.compile(r"\bxapp-[0-9]+-[a-zA-Z0-9]+")),
    ("SLACK_LEGACY_TOKEN", re.compile(r"\bxox[prs]-[a-zA-Z0-9\-]+")),
    # Google / GCP
    ("GOOGLE_API_KEY", re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b")),
    ("GOOGLE_OAUTH_SECRET", re.compile(r"\bGOCSPX-[a-zA-Z0-9\-_]+")),
    ("GCP_SERVICE_ACCOUNT", re.compile(r'"type"\s*:\s*"service_account"')),
    # GitLab
    ("GITLAB_PERSONAL_TOKEN", re.compile(r"\bglpat-[a-zA-Z0-9\-_]{20,}\b")),
    # Generic high-entropy passwords / secrets in common assignment patterns
    (
        "GENERIC_PASSWORD",
        re.compile(r'(?i)(?:password|passwd|pwd|secret|token|api[_\-]?key)\s*[=:]\s*["\']([^"\']{8,})["\']'),
    ),
    # Private keys (PEM headers)
    ("PRIVATE_KEY_RSA", re.compile(r"-----BEGIN RSA PRIVATE KEY-----")),
    ("PRIVATE_KEY_EC", re.compile(r"-----BEGIN EC PRIVATE KEY-----")),
    ("PRIVATE_KEY_PKCS8", re.compile(r"-----BEGIN PRIVATE KEY-----")),
    ("PRIVATE_KEY_OPENSSH", re.compile(r"-----BEGIN OPENSSH PRIVATE KEY-----")),
    ("PRIVATE_KEY_PGP", re.compile(r"-----BEGIN PGP PRIVATE KEY BLOCK-----")),
    # Database connection strings
    ("DATABASE_URL", re.compile(r"(?i)(?:postgres(?:ql)?|mysql|mongodb|redis)://[^:\s]+:[^@\s]+@[^\s]+")),
    # JWT tokens (3-part base64url structure)
    ("JWT_TOKEN", re.compile(r"\beyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\b")),
    # Bearer tokens in HTTP headers
    ("HTTP_BEARER_TOKEN", re.compile(r'(?i)Authorization\s*[=:]\s*["\']?Bearer\s+[a-zA-Z0-9\-._~+/]{20,}')),
    # HashiCorp Vault tokens
    ("VAULT_TOKEN", re.compile(r"\bs\.([a-zA-Z0-9]{24})\b")),
    ("VAULT_ROLE_ID", re.compile(r"\broot\.[a-zA-Z0-9]{24}\b")),
    # npm auth tokens
    ("NPM_AUTH_TOKEN", re.compile(r"//registry\.npmjs\.org/:_authToken=[a-zA-Z0-9\-_]+")),
    # Stripe keys
    ("STRIPE_SECRET_KEY", re.compile(r"\bsk_live_[a-zA-Z0-9]{24}\b")),
    ("STRIPE_TEST_KEY", re.compile(r"\bsk_test_[a-zA-Z0-9]{24}\b")),
    # Twilio
    ("TWILIO_AUTH_TOKEN", re.compile(r"(?i)twilio.*auth.*token\s*[=:]\s*[a-f0-9]{32}")),
    # Sendgrid
    ("SENDGRID_API_KEY", re.compile(r"\bSG\.[a-zA-Z0-9]{22}\.[a-zA-Z0-9]{43}\b")),
]

#: Inline suppression comment — any line containing this string is skipped.
_SUPPRESS_COMMENT = "secret-scanner:ignore"

#: File extensions to skip unconditionally (binary / generated / large).
_SKIP_EXTENSIONS = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".bmp",
        ".ico",
        ".svg",
        ".pdf",
        ".zip",
        ".tar",
        ".gz",
        ".bz2",
        ".xz",
        ".whl",
        ".egg",
        ".pyc",
        ".pyo",
        ".pyd",
        ".so",
        ".dll",
        ".exe",
        ".bin",
        ".ttf",
        ".woff",
        ".woff2",
        ".eot",
        ".lock",  # lockfiles contain hash strings that resemble secrets
    }
)

#: Maximum file size (bytes) to read; larger files are skipped.
_MAX_FILE_SIZE = 2 * 1024 * 1024  # 2 MiB


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class SecretFinding:
    """A single potential secret found in a file."""

    file_path: str  # Relative or absolute path as provided
    line_number: int  # 1-based line number
    pattern_label: str  # Human-readable pattern name (e.g. "AWS_ACCESS_KEY_ID")
    matched_text: str  # Redacted excerpt (first 40 chars of match, then "…")
    severity: str  # "critical" | "high" | "medium"


@dataclass
class ScanSummary:
    """Aggregated summary of a secret scan run."""

    scanned_at: str
    root_path: str
    files_scanned: int
    files_skipped: int
    total_findings: int
    critical: int
    high: int
    medium: int
    findings: list[SecretFinding] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Severity mapping
# ---------------------------------------------------------------------------

#: Override default "high" for specific pattern labels.
_SEVERITY_MAP: dict[str, str] = {
    "AWS_ACCESS_KEY_ID": "critical",
    "AWS_SECRET_ACCESS_KEY": "critical",
    "GITHUB_TOKEN_PAT": "critical",
    "GITHUB_TOKEN_OAUTH": "critical",
    "GITHUB_TOKEN_APP": "critical",
    "GITHUB_TOKEN_REFRESH": "critical",
    "OPENAI_API_KEY": "critical",
    "ANTHROPIC_API_KEY": "critical",
    "STRIPE_SECRET_KEY": "critical",
    "PRIVATE_KEY_RSA": "critical",
    "PRIVATE_KEY_EC": "critical",
    "PRIVATE_KEY_PKCS8": "critical",
    "PRIVATE_KEY_OPENSSH": "critical",
    "PRIVATE_KEY_PGP": "critical",
    "GCP_SERVICE_ACCOUNT": "high",
    "GITLAB_PERSONAL_TOKEN": "high",
    "DATABASE_URL": "high",
    "JWT_TOKEN": "high",
    "HTTP_BEARER_TOKEN": "high",
    "VAULT_TOKEN": "high",
    "SLACK_BOT_TOKEN": "high",
    "GENERIC_PASSWORD": "medium",
    "NPM_AUTH_TOKEN": "medium",
    "STRIPE_TEST_KEY": "medium",
    "VAULT_ROLE_ID": "medium",
}

_DEFAULT_SEVERITY = "high"


def _severity(label: str) -> str:
    return _SEVERITY_MAP.get(label, _DEFAULT_SEVERITY)


# ---------------------------------------------------------------------------
# Allow-list helpers
# ---------------------------------------------------------------------------


def _load_allowlist(path: Path) -> set[str]:
    """Load an allow-list JSON file.

    Format::

        {
          "paths": ["path/to/file.py", "tests/fixtures/"],
          "patterns": ["STRIPE_TEST_KEY"]
        }

    Returns a set of lower-cased absolute path strings and pattern labels.
    """
    if not path.exists():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    result: set[str] = set()
    for p in data.get("paths", []):
        result.add(str(Path(p).resolve()).lower())
    for label in data.get("patterns", []):
        result.add(label.upper())
    return result


def _is_allowlisted(
    file_path: Path,
    label: str,
    allowlist: set[str],
) -> bool:
    """Return True if this finding should be suppressed by the allow-list."""
    abs_str = str(file_path.resolve()).lower()
    if label.upper() in allowlist:
        return True
    return any(entry in abs_str for entry in allowlist)


# ---------------------------------------------------------------------------
# Core scanner
# ---------------------------------------------------------------------------


class SecretScanner:
    """Scan files and directories for potential leaked secrets.

    Args:
        allowlist_path: Optional path to a JSON allow-list file.
        allowlist_entries: Optional set of pre-loaded allow-list strings.
        extra_patterns: Optional additional (label, pattern) tuples to include.
        max_file_size: Files larger than this (bytes) are skipped.
    """

    def __init__(
        self,
        allowlist_path: Path | None = None,
        allowlist_entries: set[str] | None = None,
        extra_patterns: list[tuple[str, re.Pattern[str]]] | None = None,
        max_file_size: int = _MAX_FILE_SIZE,
    ) -> None:
        self._allowlist: set[str] = allowlist_entries or set()
        if allowlist_path:
            self._allowlist |= _load_allowlist(allowlist_path)

        self._patterns: list[tuple[str, re.Pattern[str]]] = list(_SECRET_PATTERNS)
        if extra_patterns:
            self._patterns.extend(extra_patterns)

        self._max_file_size = max_file_size
        self._findings: list[SecretFinding] = []
        self._errors: list[str] = []
        self._files_scanned: int = 0
        self._files_skipped: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scan_file(self, path: Path) -> list[SecretFinding]:
        """Scan a single file for secrets.

        Args:
            path: Path to the file to scan.

        Returns:
            List of SecretFinding objects found in this file.
        """
        findings: list[SecretFinding] = []

        if not path.is_file():
            self._errors.append(f"Not a file: {path}")
            return findings

        if path.suffix.lower() in _SKIP_EXTENSIONS:
            self._files_skipped += 1
            return findings

        try:
            size = path.stat().st_size
        except OSError as exc:
            self._errors.append(f"stat failed: {path}: {exc}")
            self._files_skipped += 1
            return findings

        if size > self._max_file_size:
            self._files_skipped += 1
            return findings

        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            self._errors.append(f"read failed: {path}: {exc}")
            self._files_skipped += 1
            return findings

        self._files_scanned += 1

        for lineno, line in enumerate(content.splitlines(), start=1):
            # Honour inline suppression comment
            if _SUPPRESS_COMMENT in line:
                continue

            for label, pattern in self._patterns:
                match = pattern.search(line)
                if not match:
                    continue

                if _is_allowlisted(path, label, self._allowlist):
                    continue

                # Redact: show at most 40 chars of the raw match
                raw = match.group(0)
                excerpt = (raw[:40] + "…") if len(raw) > 40 else raw

                finding = SecretFinding(
                    file_path=str(path),
                    line_number=lineno,
                    pattern_label=label,
                    matched_text=excerpt,
                    severity=_severity(label),
                )
                findings.append(finding)
                self._findings.append(finding)

                # One finding per pattern per line — avoid duplicates
                break

        return findings

    def scan_directory(self, path: Path) -> list[SecretFinding]:
        """Recursively scan all files under *path* for secrets.

        Args:
            path: Root directory to scan.

        Returns:
            Aggregated list of all SecretFinding objects.
        """
        if not path.is_dir():
            self._errors.append(f"Not a directory: {path}")
            return []

        findings: list[SecretFinding] = []
        for child in sorted(path.rglob("*")):
            if child.is_file():
                findings.extend(self.scan_file(child))
        return findings

    def get_findings(self) -> list[SecretFinding]:
        """Return all findings accumulated across all scan_file / scan_directory calls."""
        return list(self._findings)

    def get_summary(self, root_path: str = ".") -> ScanSummary:
        """Build a ScanSummary from the accumulated scan state.

        Args:
            root_path: Label for the root path used (informational only).

        Returns:
            ScanSummary dataclass.
        """
        counts = {"critical": 0, "high": 0, "medium": 0}
        for f in self._findings:
            counts[f.severity] = counts.get(f.severity, 0) + 1

        return ScanSummary(
            scanned_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            root_path=root_path,
            files_scanned=self._files_scanned,
            files_skipped=self._files_skipped,
            total_findings=len(self._findings),
            critical=counts.get("critical", 0),
            high=counts.get("high", 0),
            medium=counts.get("medium", 0),
            findings=list(self._findings),
            errors=list(self._errors),
        )

    def reset(self) -> None:
        """Clear all accumulated state (findings, errors, counters)."""
        self._findings.clear()
        self._errors.clear()
        self._files_scanned = 0
        self._files_skipped = 0


# ---------------------------------------------------------------------------
# Convenience module-level functions
# ---------------------------------------------------------------------------


def scan_file(
    path: Path,
    allowlist_path: Path | None = None,
    allowlist_entries: set[str] | None = None,
) -> list[SecretFinding]:
    """Scan a single file.  Convenience wrapper around SecretScanner."""
    scanner = SecretScanner(
        allowlist_path=allowlist_path,
        allowlist_entries=allowlist_entries,
    )
    return scanner.scan_file(path)


def scan_directory(
    path: Path,
    allowlist_path: Path | None = None,
    allowlist_entries: set[str] | None = None,
) -> ScanSummary:
    """Scan a directory recursively.  Convenience wrapper around SecretScanner."""
    scanner = SecretScanner(
        allowlist_path=allowlist_path,
        allowlist_entries=allowlist_entries,
    )
    scanner.scan_directory(path)
    return scanner.get_summary(root_path=str(path))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(description="SSID Secret Scanner")
    parser.add_argument("--path", type=Path, required=True, help="File or directory to scan")
    parser.add_argument("--allowlist", type=Path, default=None, help="Path to allow-list JSON file")
    parser.add_argument("--output", "-o", type=Path, default=None, help="Write JSON report to this path")
    parser.add_argument("--fail-on-findings", action="store_true", help="Exit non-zero if any secrets are found")
    parser.add_argument(
        "--min-severity",
        choices=["critical", "high", "medium"],
        default="medium",
        help="Minimum severity to report (default: medium)",
    )
    args = parser.parse_args(argv)

    scanner = SecretScanner(allowlist_path=args.allowlist)

    if args.path.is_file():
        scanner.scan_file(args.path)
    elif args.path.is_dir():
        scanner.scan_directory(args.path)
    else:
        print(f"ERROR: path not found: {args.path}", file=sys.stderr)
        return 2

    summary = scanner.get_summary(root_path=str(args.path))

    # Filter by minimum severity
    severity_order = {"critical": 3, "high": 2, "medium": 1}
    min_rank = severity_order.get(args.min_severity, 1)
    summary.findings = [f for f in summary.findings if severity_order.get(f.severity, 0) >= min_rank]

    report = asdict(summary)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"Secret scan report written to {args.output}")
    else:
        print(json.dumps(report, indent=2))

    print(
        f"\nSummary: {summary.total_findings} finding(s) in "
        f"{summary.files_scanned} file(s) "
        f"(critical={summary.critical}, high={summary.high}, medium={summary.medium})",
        file=sys.stderr,
    )

    if args.fail_on_findings and summary.total_findings > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
