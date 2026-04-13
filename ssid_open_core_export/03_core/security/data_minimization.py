#!/usr/bin/env python3
"""
SSID Data Minimization & Redaction Module v4.1
Hard requirement: No data collection as orchestration byproduct

Secret patterns delegated to ssid_security (generated from SSID-EMS SoT).
"""

from __future__ import annotations

import datetime
import hashlib
import os
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


# -- Deterministic repo-root discovery --------------------------------------
def _find_repo_root(start: Path, max_depth: int = 10) -> Path:
    """Walk up from start until .git/ or 16_codex/ marker found."""
    current = start.resolve()
    for _ in range(max_depth):
        if (current / ".git").exists() or (current / "16_codex").exists():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    raise RuntimeError("SSID repo root not found (no .git or 16_codex marker)")


def _bootstrap_security_import() -> None:
    sec_path = str(_find_repo_root(Path(__file__)) / "03_core" / "security")
    if sec_path not in sys.path:
        sys.path.insert(0, sec_path)


_bootstrap_security_import()
from ssid_security.secret_patterns import redact as _redact_secrets

# -- End bootstrap ----------------------------------------------------------


@dataclass
class RedactionRule:
    """Redaction rule for sensitive data patterns"""

    name: str
    pattern: str
    replacement: str
    description: str


class SSIDRedactor:
    """Redacts secrets/PII from all outputs per SSID requirements"""

    # PII rules (local, not delegated to ssid_security)
    # Secret detection (AWS, GitHub, Stripe, etc.) is handled by ssid_security
    REDACTION_RULES = [
        RedactionRule(
            name="email",
            pattern=r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            replacement="[EMAIL_REDACTED]",
            description="Email addresses",
        ),
        RedactionRule(
            name="ip_address",
            pattern=r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b",
            replacement="[IP_REDACTED]",
            description="IPv4 addresses",
        ),
        RedactionRule(
            name="sensitive_url",
            pattern=r"https?://[^\s]*?(api|token|key|secret|auth)[^\s]*",
            replacement="[URL_REDACTED]",
            description="URLs with sensitive parameters",
        ),
        RedactionRule(
            name="sensitive_path",
            pattern=r"[^\s]*?/(?:private|secret|key|token|\.env|\.creds?)[^\s]*",
            replacement="[PATH_REDACTED]",
            description="Sensitive file paths",
        ),
        RedactionRule(
            name="uuid",
            pattern=r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
            replacement="[UUID_REDACTED]",
            description="UUID identifiers",
        ),
        RedactionRule(
            name="certificate",
            pattern=r"(?i)(-----BEGIN\s+CERTIFICATE-----.*?-----END\s+CERTIFICATE-----)",
            replacement="[CERTIFICATE_REDACTED]",
            description="Certificate blocks",
        ),
        RedactionRule(
            name="personal_name",
            pattern=r"\b[A-Z][a-z]+\s+[A-Z][a-z]+\b",
            replacement="[NAME_REDACTED]",
            description="Personal names (basic)",
        ),
        RedactionRule(
            name="phone",
            pattern=r"\+?1?[-.\s]?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}",
            replacement="[PHONE_REDACTED]",
            description="Phone numbers",
        ),
        RedactionRule(
            name="credit_card",
            pattern=r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
            replacement="[CARD_REDACTED]",
            description="Credit card numbers",
        ),
        RedactionRule(
            name="ssn",
            pattern=r"\b\d{3}-\d{2}-\d{4}\b",
            replacement="[SSN_REDACTED]",
            description="Social Security Numbers",
        ),
    ]

    def __init__(self, log_mode: str = "MINIMAL"):
        self.log_mode = log_mode.upper()
        self.redaction_stats = {"total_redactions": 0, "rules_applied": {rule.name: 0 for rule in self.REDACTION_RULES}}

    def redact_text(self, text: str) -> str:
        """Apply all redaction rules to text.

        Step 1: Delegate secret redaction to ssid_security (generated from EMS).
        Step 2: Apply local PII rules.
        """
        if not text:
            return text

        # Secrets via ssid_security (generated artifact)
        redacted_text, secret_count = _redact_secrets(text)
        if secret_count:
            self.redaction_stats["total_redactions"] += secret_count

        # PII via local rules
        for rule in self.REDACTION_RULES:
            matches = re.findall(rule.pattern, redacted_text, re.DOTALL | re.IGNORECASE)
            if matches:
                redacted_text = re.sub(rule.pattern, rule.replacement, redacted_text, flags=re.DOTALL | re.IGNORECASE)
                self.redaction_stats["rules_applied"][rule.name] += len(matches)
                self.redaction_stats["total_redactions"] += len(matches)

        return redacted_text

    def redact_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """Recursively redact sensitive data in dictionary"""
        if not isinstance(data, dict):
            return data

        redacted = {}
        for key, value in data.items():
            if isinstance(value, str):
                redacted[key] = self.redact_text(value)
            elif isinstance(value, dict):
                redacted[key] = self.redact_dict(value)
            elif isinstance(value, list):
                redacted[key] = [self.redact_text(item) if isinstance(item, str) else item for item in value]
            else:
                redacted[key] = value

        return redacted

    def create_safe_summary(self, full_text: str, max_lines: int = 20) -> str:
        """Create safe summary with redaction and length limits"""
        if not full_text:
            return ""

        # Apply redaction first
        redacted_text = self.redact_text(full_text)

        # Split into lines and limit
        lines = redacted_text.splitlines()
        if len(lines) <= max_lines:
            return redacted_text

        # Take first and last lines with indicator
        summary_lines = (
            lines[: max_lines // 2] + [f"... [{len(lines) - max_lines} lines omitted] ..."] + lines[-(max_lines // 2) :]
        )
        return "\\n".join(summary_lines)

    def hash_sensitive_content(self, content: str) -> str:
        """Create hash of sensitive content for audit purposes"""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def get_redaction_report(self) -> dict[str, Any]:
        """Get redaction statistics report"""
        return {
            "log_mode": self.log_mode,
            "redaction_timestamp": datetime.datetime.now(datetime.UTC)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z"),
            "total_redactions": self.redaction_stats["total_redactions"],
            "rules_applied": {k: v for k, v in self.redaction_stats["rules_applied"].items() if v > 0},
            "active_rules": len([r for r in self.REDACTION_RULES if self.redaction_stats["rules_applied"][r.name] > 0]),
        }


class SSIDDataMinimizer:
    """Enforces SSID data minimization requirements"""

    def __init__(self, log_mode: str = "MINIMAL"):
        self.log_mode = log_mode.upper()
        self.redactor = SSIDRedactor(log_mode)

        # Environment enforcement
        os.environ["LOG_MODE"] = self.log_mode
        os.environ["NO_PROMPT_PERSIST"] = "true"
        os.environ["NO_STDOUT_PERSIST"] = "true"

    def should_persist_prompt(self) -> bool:
        """Check if prompts should be persisted (FORENSIC mode only)"""
        return self.log_mode == "FORENSIC"

    def should_persist_stdout(self) -> bool:
        """Check if stdout should be persisted (FORENSIC mode only)"""
        return self.log_mode == "FORENSIC"

    def create_minimal_evidence(
        self, task_id: str, patch_content: str, gate_results: list[dict[str, Any]], changed_files: list[str]
    ) -> dict[str, Any]:
        """Create minimal evidence bundle with hash-only storage"""

        # Hash the patch content (don't store full content in MINIMAL mode)
        patch_hash = hashlib.sha256(patch_content.encode("utf-8")).hexdigest()

        # Create minimal evidence
        evidence = {
            "task_id": task_id,
            "evidence_mode": self.log_mode,
            "generated_utc": datetime.datetime.now(datetime.UTC)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z"),
            "security_context": "ROOT-24-LOCK",
            # Hash-only build evidence
            "patch": {
                "sha256": patch_hash,
                "bytes": len(patch_content.encode("utf-8")),
                "lines": len(patch_content.splitlines()),
            },
            # Minimal runtime data
            "runtime": {
                "tool_used": "unknown",  # To be filled by caller
                "exit_code": 0,  # To be filled by caller
                "duration_seconds": 0,  # To be filled by caller
                "started_utc": "",  # To be filled by caller
                "completed_utc": "",  # To be filled by caller
            },
            # Scope without content
            "scope": {
                "allowed_paths": [],  # To be filled by caller
                "changed_files": changed_files,
                "file_count": len(changed_files),
            },
            # Gate results (minimal)
            "gates": {
                "total": len(gate_results),
                "passed": len([g for g in gate_results if g.get("status") == "PASS"]),
                "failed": len([g for g in gate_results if g.get("status") == "FAIL"]),
                "overall_status": "PASS" if all(g.get("status") == "PASS" for g in gate_results) else "FAIL",
            },
            # Redaction report
            "redaction": self.redactor.get_redaction_report(),
        }

        return evidence

    def process_agent_output(self, stdout: str, stderr: str, prompt: str = "") -> tuple[str, str, str | None]:
        """Process agent output according to data minimization rules"""

        processed_stdout = ""
        processed_stderr = ""
        prompt_hash = None

        # Process stdout
        if self.should_persist_stdout():
            # FORENSIC mode: store redacted full output
            processed_stdout = self.redactor.redact_text(stdout)
        else:
            # MINIMAL mode: store only safe summary
            processed_stdout = self.redactor.create_safe_summary(stdout, max_lines=20)

        # Process stderr (always minimal)
        processed_stderr = self.redactor.create_safe_summary(stderr, max_lines=10)

        # Process prompt (hash-only in any mode)
        if prompt:
            prompt_hash = self.redactor.hash_sensitive_content(prompt)
            if self.should_persist_prompt():
                # FORENSIC mode: also store redacted prompt
                self.redactor.redact_text(prompt)
                # Add to evidence if needed

        return processed_stdout, processed_stderr, prompt_hash

    def cleanup_temporary_data(self, temp_paths: list[Path]) -> None:
        """Clean up temporary data after task completion"""
        for temp_path in temp_paths:
            try:
                if temp_path.exists():
                    if temp_path.is_file():
                        temp_path.unlink()
                    elif temp_path.is_dir():
                        shutil.rmtree(temp_path)
            except Exception as e:
                print(f"WARNING: Could not cleanup {temp_path}: {e}", file=sys.stderr)


# Global instance for easy access
_data_minimizer = None


def get_data_minimizer(log_mode: str = "MINIMAL") -> SSIDDataMinimizer:
    """Get global data minimizer instance"""
    global _data_minimizer
    if _data_minimizer is None or _data_minimizer.log_mode != log_mode.upper():
        _data_minimizer = SSIDDataMinimizer(log_mode)
    return _data_minimizer


def enforce_data_minimization(log_mode: str = "MINIMAL") -> SSIDDataMinimizer:
    """Enforce data minimization as hard requirement"""
    minimizer = get_data_minimizer(log_mode)

    # Set environment variables
    os.environ["LOG_MODE"] = log_mode
    os.environ["NO_PROMPT_PERSIST"] = "true"
    os.environ["NO_STDOUT_PERSIST"] = "true"

    return minimizer


# Convenience functions
def redact_text(text: str, log_mode: str = "MINIMAL") -> str:
    """Redact text using appropriate redactor"""
    redactor = SSIDRedactor(log_mode)
    return redactor.redact_text(text)


def create_safe_summary(text: str, max_lines: int = 20, log_mode: str = "MINIMAL") -> str:
    """Create safe summary with redaction"""
    redactor = SSIDRedactor(log_mode)
    return redactor.create_safe_summary(text, max_lines)


def hash_content(content: str) -> str:
    """Hash content for audit purposes"""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
