#!/usr/bin/env python3
"""Production Readiness Checker — pre-launch verification gate.

Runs a comprehensive suite of checks to determine whether the SSID
repository is ready for production deployment:

  1. All tests green (pytest)
  2. Secret scan clean
  3. PII scan clean
  4. Charts complete (385/385)
  5. Manifests complete (24/24)
  6. Convergence pass
  7. Evidence present (WORM)
  8. Gates pass
  9. ROOT-24-LOCK compliant
 10. No placeholder files remain

Output: JSON report with per-check results and overall verdict.

Verdict:
  READY         — all checks pass
  NOT_READY     — one or more checks fail
  CONDITIONAL   — no fails but one or more warnings

Exit codes:
  0 = READY
  1 = CONDITIONAL
  2 = NOT_READY
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional

EXIT_READY = 0
EXIT_CONDITIONAL = 1
EXIT_NOT_READY = 2

REPO_ROOT = Path(__file__).resolve().parents[2]

EXPECTED_CHART_COUNT = 385
EXPECTED_MANIFEST_COUNT = 24
PLACEHOLDER_SIZE = 49

ROOTS_24 = [
    "01_ai_layer", "02_audit_logging", "03_core", "04_deployment",
    "05_documentation", "06_data_pipeline", "07_governance_legal",
    "08_identity_score", "09_meta_identity", "10_interoperability",
    "11_test_simulation", "12_tooling", "13_ui_layer", "14_zero_time_auth",
    "15_infra", "16_codex", "17_observability", "18_data_layer",
    "19_adapters", "20_foundation", "21_post_quantum_crypto",
    "22_datasets", "23_compliance", "24_meta_orchestration",
]

# Patterns that indicate plaintext secrets
SECRET_PATTERNS = [
    re.compile(r"(?:password|passwd|pwd)\s*[:=]\s*['\"][^'\"]{4,}['\"]", re.IGNORECASE),
    re.compile(r"(?:api[_-]?key|apikey)\s*[:=]\s*['\"][^'\"]{8,}['\"]", re.IGNORECASE),
    re.compile(r"(?:secret[_-]?key|secret)\s*[:=]\s*['\"][^'\"]{8,}['\"]", re.IGNORECASE),
    re.compile(r"(?:access[_-]?token|auth[_-]?token|bearer)\s*[:=]\s*['\"][^'\"]{8,}['\"]", re.IGNORECASE),
    re.compile(r"-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----"),
    re.compile(r"ghp_[A-Za-z0-9_]{36,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
]

# Patterns that indicate PII
PII_PATTERNS = [
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),  # SSN
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),  # email
    re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),  # phone
    re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"),  # credit card
]

# Directories/files to skip during scans
SCAN_SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", ".ssid_sandbox"}
SCAN_EXTENSIONS = {".py", ".yaml", ".yml", ".json", ".toml", ".cfg", ".ini", ".env", ".sh", ".bat", ".ps1"}


@dataclass
class ReadinessCheck:
    """Result of a single production readiness check."""
    name: str
    category: str
    status: str  # "pass" | "fail" | "warn"
    detail: str
    evidence_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ReadinessReport:
    """Aggregate production readiness report."""
    timestamp: str = ""
    verdict: str = "NOT_READY"  # READY | NOT_READY | CONDITIONAL
    checks: List[ReadinessCheck] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "verdict": self.verdict,
            "summary": self.summary,
            "checks": [c.to_dict() for c in self.checks],
        }


def _sha256(data: str) -> str:
    """Return SHA-256 hex digest of a string."""
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _scan_files(repo: Path, patterns: list[re.Pattern], skip_dirs: set[str] | None = None,
                extensions: set[str] | None = None) -> list[dict[str, Any]]:
    """Scan repo files for regex patterns, returning matches."""
    if skip_dirs is None:
        skip_dirs = SCAN_SKIP_DIRS
    if extensions is None:
        extensions = SCAN_EXTENSIONS
    findings: list[dict[str, Any]] = []
    for p in repo.rglob("*"):
        if not p.is_file():
            continue
        if any(skip in p.parts for skip in skip_dirs):
            continue
        if p.suffix not in extensions:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except (OSError, UnicodeDecodeError):
            continue
        for pattern in patterns:
            for match in pattern.finditer(text):
                findings.append({
                    "file": str(p.relative_to(repo)),
                    "pattern": pattern.pattern[:60],
                    "line": text[:match.start()].count("\n") + 1,
                })
    return findings


class ProductionReadinessChecker:
    """Runs all production readiness checks against the SSID repository."""

    def __init__(self, repo_root: Path | None = None) -> None:
        self.repo = (repo_root or REPO_ROOT).resolve()
        self.checks: list[ReadinessCheck] = []

    def _add(self, name: str, category: str, status: str, detail: str) -> ReadinessCheck:
        evidence = _sha256(f"{name}:{status}:{detail}")
        check = ReadinessCheck(
            name=name,
            category=category,
            status=status,
            detail=detail,
            evidence_hash=evidence,
        )
        self.checks.append(check)
        return check

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    def check_all_tests_green(self) -> ReadinessCheck:
        """Run pytest and verify all tests pass."""
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", "--tb=no"],
                capture_output=True, text=True, cwd=str(self.repo),
                timeout=300,
            )
            output = result.stdout.strip()
            if result.returncode == 0:
                # Extract pass count from pytest output like "42 passed"
                m = re.search(r"(\d+)\s+passed", output)
                count = m.group(1) if m else "?"
                return self._add("all_tests_green", "testing",
                                 "pass", f"{count} tests passed")
            else:
                # Extract failure info
                lines = (result.stdout + result.stderr).strip().split("\n")
                summary = lines[-1] if lines else "pytest failed"
                return self._add("all_tests_green", "testing",
                                 "fail", f"pytest failed: {summary[:200]}")
        except subprocess.TimeoutExpired:
            return self._add("all_tests_green", "testing",
                             "fail", "pytest timed out after 300s")
        except FileNotFoundError:
            return self._add("all_tests_green", "testing",
                             "fail", "pytest not found")

    def check_secret_scan_clean(self) -> ReadinessCheck:
        """Scan repository for plaintext secrets."""
        findings = _scan_files(self.repo, SECRET_PATTERNS)
        if not findings:
            return self._add("secret_scan_clean", "security",
                             "pass", "no plaintext secrets detected")
        # Redact details — only report counts and file paths
        files = sorted(set(f["file"] for f in findings))
        return self._add("secret_scan_clean", "security",
                         "fail", f"{len(findings)} potential secret(s) in {len(files)} file(s): {', '.join(files[:5])}")

    def check_pii_scan_clean(self) -> ReadinessCheck:
        """Scan repository for PII patterns."""
        findings = _scan_files(self.repo, PII_PATTERNS)
        if not findings:
            return self._add("pii_scan_clean", "security",
                             "pass", "no PII patterns detected")
        files = sorted(set(f["file"] for f in findings))
        return self._add("pii_scan_clean", "security",
                         "warn", f"{len(findings)} potential PII pattern(s) in {len(files)} file(s): {', '.join(files[:5])}")

    def check_charts_complete(self) -> ReadinessCheck:
        """Verify 385/385 chart.yaml files exist on draft."""
        charts = list(self.repo.rglob("chart.yaml"))
        # Filter to only shard charts (inside shards/ directories)
        shard_charts = [c for c in charts if "shards" in c.parts]
        count = len(shard_charts)
        if count >= EXPECTED_CHART_COUNT:
            return self._add("charts_complete", "completeness",
                             "pass", f"{count}/{EXPECTED_CHART_COUNT} charts present")
        elif count >= EXPECTED_CHART_COUNT * 0.9:
            return self._add("charts_complete", "completeness",
                             "warn", f"{count}/{EXPECTED_CHART_COUNT} charts present (>90%)")
        else:
            return self._add("charts_complete", "completeness",
                             "fail", f"{count}/{EXPECTED_CHART_COUNT} charts present")

    def check_manifests_complete(self) -> ReadinessCheck:
        """Verify 24/24 root manifest.yaml files exist."""
        count = 0
        missing: list[str] = []
        for root_name in ROOTS_24:
            manifest = self.repo / root_name / "manifest.yaml"
            if manifest.is_file():
                count += 1
            else:
                missing.append(root_name)
        if count == EXPECTED_MANIFEST_COUNT:
            return self._add("manifests_complete", "completeness",
                             "pass", f"{count}/{EXPECTED_MANIFEST_COUNT} manifests present")
        else:
            return self._add("manifests_complete", "completeness",
                             "fail", f"{count}/{EXPECTED_MANIFEST_COUNT} manifests present; missing: {', '.join(missing[:5])}")

    def check_convergence_pass(self) -> ReadinessCheck:
        """Run convergence checker and verify pass."""
        convergence_script = self.repo / "12_tooling" / "cli" / "convergence_checker.py"
        if not convergence_script.is_file():
            return self._add("convergence_pass", "consistency",
                             "fail", "convergence_checker.py not found")
        try:
            result = subprocess.run(
                [sys.executable, str(convergence_script), "--json"],
                capture_output=True, text=True, cwd=str(self.repo),
                timeout=120,
            )
            if result.returncode == 0:
                return self._add("convergence_pass", "consistency",
                                 "pass", "convergence checker passed")
            elif result.returncode == 1:
                return self._add("convergence_pass", "consistency",
                                 "warn", "convergence checker returned warnings")
            else:
                summary = result.stdout.strip().split("\n")[-1] if result.stdout.strip() else "check failed"
                return self._add("convergence_pass", "consistency",
                                 "fail", f"convergence checker failed: {summary[:200]}")
        except (subprocess.TimeoutExpired, OSError) as exc:
            return self._add("convergence_pass", "consistency",
                             "fail", f"convergence checker error: {exc}")

    def check_evidence_present(self) -> ReadinessCheck:
        """Verify WORM evidence exists at canonical paths."""
        evidence_dirs = [
            self.repo / "02_audit_logging" / "evidence",
            self.repo / "02_audit_logging" / "reports",
        ]
        found = 0
        for d in evidence_dirs:
            if d.is_dir():
                found += sum(1 for _ in d.iterdir() if _.is_file())
        if found > 0:
            return self._add("evidence_present", "audit",
                             "pass", f"{found} evidence file(s) found")
        else:
            return self._add("evidence_present", "audit",
                             "fail", "no WORM evidence files found")

    def check_gates_pass(self) -> ReadinessCheck:
        """Verify all gates green by running run_all_gates.py."""
        gate_script = self.repo / "12_tooling" / "cli" / "run_all_gates.py"
        if not gate_script.is_file():
            return self._add("gates_pass", "gates",
                             "fail", "run_all_gates.py not found")
        try:
            result = subprocess.run(
                [sys.executable, str(gate_script)],
                capture_output=True, text=True, cwd=str(self.repo),
                timeout=300,
            )
            if result.returncode == 0:
                return self._add("gates_pass", "gates",
                                 "pass", "all gates passed")
            else:
                summary = result.stdout.strip().split("\n")[-1] if result.stdout.strip() else "gates failed"
                return self._add("gates_pass", "gates",
                                 "fail", f"gate failures detected: {summary[:200]}")
        except (subprocess.TimeoutExpired, OSError) as exc:
            return self._add("gates_pass", "gates",
                             "fail", f"gate runner error: {exc}")

    def check_root24_lock(self) -> ReadinessCheck:
        """Verify ROOT-24-LOCK structure compliance."""
        # Check that exactly 24 root directories exist and no extras
        actual_roots = []
        extra_dirs = []
        for entry in sorted(self.repo.iterdir()):
            if not entry.is_dir():
                continue
            if entry.name.startswith("."):
                continue
            # Root dirs follow NN_name pattern
            if re.match(r"^\d{2}_", entry.name):
                actual_roots.append(entry.name)
                if entry.name not in ROOTS_24:
                    extra_dirs.append(entry.name)

        missing = [r for r in ROOTS_24 if r not in actual_roots]

        if not missing and not extra_dirs:
            return self._add("root24_lock", "structure",
                             "pass", f"ROOT-24-LOCK verified: {len(actual_roots)} roots")
        else:
            parts = []
            if missing:
                parts.append(f"missing: {', '.join(missing[:5])}")
            if extra_dirs:
                parts.append(f"extra: {', '.join(extra_dirs[:5])}")
            return self._add("root24_lock", "structure",
                             "fail", f"ROOT-24-LOCK violation: {'; '.join(parts)}")

    def check_no_placeholders(self) -> ReadinessCheck:
        """Verify no 49-byte placeholder files remain."""
        placeholders: list[str] = []
        for p in self.repo.rglob("*"):
            if not p.is_file():
                continue
            if any(skip in p.parts for skip in SCAN_SKIP_DIRS):
                continue
            try:
                if p.stat().st_size == PLACEHOLDER_SIZE:
                    content = p.read_bytes()
                    # Common placeholder pattern: single-line stub text
                    if content.strip() and len(content.strip().split(b"\n")) <= 2:
                        placeholders.append(str(p.relative_to(self.repo)))
            except OSError:
                continue

        if not placeholders:
            return self._add("no_placeholders", "completeness",
                             "pass", "no 49-byte placeholder files found")
        else:
            return self._add("no_placeholders", "completeness",
                             "warn", f"{len(placeholders)} potential placeholder(s): {', '.join(placeholders[:5])}")

    # ------------------------------------------------------------------
    # Aggregate
    # ------------------------------------------------------------------

    def run_all(self) -> ReadinessReport:
        """Execute all checks and produce a readiness report."""
        self.checks.clear()

        self.check_all_tests_green()
        self.check_secret_scan_clean()
        self.check_pii_scan_clean()
        self.check_charts_complete()
        self.check_manifests_complete()
        self.check_convergence_pass()
        self.check_evidence_present()
        self.check_gates_pass()
        self.check_root24_lock()
        self.check_no_placeholders()

        return self.generate_readiness_report()

    def generate_readiness_report(self) -> ReadinessReport:
        """Build the final readiness report from collected checks."""
        pass_count = sum(1 for c in self.checks if c.status == "pass")
        fail_count = sum(1 for c in self.checks if c.status == "fail")
        warn_count = sum(1 for c in self.checks if c.status == "warn")

        if fail_count > 0:
            verdict = "NOT_READY"
        elif warn_count > 0:
            verdict = "CONDITIONAL"
        else:
            verdict = "READY"

        report = ReadinessReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            verdict=verdict,
            checks=list(self.checks),
            summary={"pass": pass_count, "fail": fail_count, "warn": warn_count, "total": len(self.checks)},
        )
        return report


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="SSID Production Readiness Checker")
    parser.add_argument("--repo", default=str(REPO_ROOT),
                        help="Path to SSID repository root")
    parser.add_argument("--json", action="store_true",
                        help="Output JSON report")
    parser.add_argument("--output", type=str, default=None,
                        help="Write report to file")
    args = parser.parse_args(argv)

    checker = ProductionReadinessChecker(Path(args.repo))
    report = checker.run_all()

    report_dict = report.to_dict()

    if args.json:
        output = json.dumps(report_dict, indent=2)
    else:
        lines = [f"Production Readiness Report — {report.timestamp}",
                 f"Verdict: {report.verdict}", ""]
        for c in report.checks:
            marker = {"pass": "PASS", "fail": "FAIL", "warn": "WARN"}[c.status]
            lines.append(f"  [{marker}] {c.name} ({c.category}): {c.detail}")
        lines.append("")
        lines.append(f"Summary: {report.summary['pass']} pass, "
                     f"{report.summary['fail']} fail, "
                     f"{report.summary['warn']} warn / "
                     f"{report.summary['total']} total")
        output = "\n".join(lines)

    print(output)

    if args.output:
        Path(args.output).write_text(
            json.dumps(report_dict, indent=2), encoding="utf-8")
        print(f"\nReport written to {args.output}")

    if report.verdict == "READY":
        return EXIT_READY
    elif report.verdict == "CONDITIONAL":
        return EXIT_CONDITIONAL
    else:
        return EXIT_NOT_READY


if __name__ == "__main__":
    sys.exit(main())
