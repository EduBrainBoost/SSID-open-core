#!/usr/bin/env python3
"""Base Guard Validator for SSID.

Module: 03_core/validators/base_guard.py
Purpose: Abstract base class for guard validators that return structured
results (bool, List[str]) instead of bare bool.

The 8 validators in 23_compliance/validators/ currently return only bool.
New validators should extend BaseGuard to provide both pass/fail status
AND a list of specific findings/reasons.

This enables:
- Audit trail: every validation failure has documented reasons
- Composability: guards can be chained with accumulated findings
- Observability: findings feed into 17_observability metrics
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Tuple


class BaseGuard(ABC):
    """Abstract base class for structured guard validators.

    All guards must return (bool, List[str]) where:
    - bool: True if validation passes, False if it fails
    - List[str]: List of findings/reasons (empty on pass, populated on fail)

    Example:
        class MyGuard(BaseGuard):
            def validate(self, data: dict) -> Tuple[bool, List[str]]:
                findings = []
                if "required_field" not in data:
                    findings.append("missing required_field")
                return (len(findings) == 0, findings)
    """

    @abstractmethod
    def validate(self, data: dict) -> Tuple[bool, List[str]]:
        """Validate data and return structured result.

        Args:
            data: Dictionary of data to validate.

        Returns:
            Tuple of (passed: bool, findings: List[str]).
            On pass: (True, [])
            On fail: (False, ["reason1", "reason2", ...])
        """
        ...

    def validate_strict(self, data: dict) -> Tuple[bool, List[str]]:
        """Validate and raise on failure. Convenience wrapper.

        Raises:
            GuardValidationError: If validation fails.
        """
        passed, findings = self.validate(data)
        if not passed:
            raise GuardValidationError(
                guard=self.__class__.__name__,
                findings=findings,
            )
        return passed, findings

    @property
    def guard_name(self) -> str:
        """Return the guard class name for logging/evidence."""
        return self.__class__.__name__


class GuardValidationError(Exception):
    """Raised when a guard validation fails in strict mode."""

    def __init__(self, guard: str, findings: List[str]) -> None:
        self.guard = guard
        self.findings = findings
        super().__init__(
            f"Guard '{guard}' failed with {len(findings)} finding(s): "
            + "; ".join(findings)
        )
