"""consumer_simulator.py — Reference EMS consumer for SSID runtime reports.

Simulates what EMS does after PR#127 merge:
1. Load a SSID runtime report from file or dict
2. Validate against JSON Schema
3. Check schema_version compatibility
4. Classify module_health
5. Classify flow_statuses (including evidence/policy decisions)
6. Return a structured ConsumerResult with exit code

Exit codes:
  0 = healthy
  1 = denied (policy violation in at least one flow)
  2 = degraded (at least one module/flow degraded, no deny)
  3 = invalid_schema (JSON Schema validation failed)
  4 = version_mismatch (MAJOR version incompatible)
  5 = incomplete (missing required fields)
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import jsonschema  # optional — gracefully degrades if missing
    _JSONSCHEMA_AVAILABLE = True
except ImportError:
    _JSONSCHEMA_AVAILABLE = False

# Expected MAJOR version — reject if report has different MAJOR
EXPECTED_MAJOR = "1"

# Status constants
FLOW_STATUS_DENIED = "denied"
FLOW_STATUS_SUCCESS = "success"
FLOW_STATUS_ERROR = "error"
FLOW_STATUS_DEGRADED = "degraded"

MODULE_STATUS_HEALTHY = "healthy"
MODULE_STATUS_DEGRADED = "degraded"
MODULE_STATUS_OFFLINE = "offline"

CONTRACT_VALID = "valid"
CONTRACT_SCHEMA_MISMATCH = "schema_mismatch"
CONTRACT_VERSION_MISMATCH = "version_mismatch"
CONTRACT_INCOMPLETE = "incomplete"

EVIDENCE_PRESENT = "present"
EVIDENCE_MISSING = "missing"
EVIDENCE_INVALID = "invalid"

# Exit codes
EXIT_HEALTHY = 0
EXIT_DENIED = 1
EXIT_DEGRADED = 2
EXIT_INVALID_SCHEMA = 3
EXIT_VERSION_MISMATCH = 4
EXIT_INCOMPLETE = 5


@dataclass
class ModuleSummary:
    total: int
    healthy: int
    degraded: int
    offline: int
    names_degraded: list[str] = field(default_factory=list)
    names_offline: list[str] = field(default_factory=list)


@dataclass
class FlowSummary:
    total: int
    successful: int
    denied: int
    error: int
    degraded: int
    flow_ids_denied: list[str] = field(default_factory=list)
    flow_ids_error: list[str] = field(default_factory=list)


@dataclass
class ConsumerResult:
    """Result of consuming a SSID runtime report."""
    exit_code: int
    contract_status: str       # CONTRACT_* constant
    overall_classification: str  # "healthy" | "denied" | "degraded" | "error"
    schema_version: str
    module_summary: ModuleSummary
    flow_summary: FlowSummary
    errors: list[str] = field(default_factory=list)

    @property
    def is_healthy(self) -> bool:
        return self.exit_code == EXIT_HEALTHY

    @property
    def is_denied(self) -> bool:
        return self.exit_code == EXIT_DENIED

    @property
    def is_degraded(self) -> bool:
        return self.exit_code == EXIT_DEGRADED

    def to_dict(self) -> dict[str, Any]:
        return {
            "exit_code": self.exit_code,
            "contract_status": self.contract_status,
            "overall_classification": self.overall_classification,
            "schema_version": self.schema_version,
            "module_summary": {
                "total": self.module_summary.total,
                "healthy": self.module_summary.healthy,
                "degraded": self.module_summary.degraded,
                "offline": self.module_summary.offline,
                "names_degraded": self.module_summary.names_degraded,
                "names_offline": self.module_summary.names_offline,
            },
            "flow_summary": {
                "total": self.flow_summary.total,
                "successful": self.flow_summary.successful,
                "denied": self.flow_summary.denied,
                "error": self.flow_summary.error,
                "degraded": self.flow_summary.degraded,
                "flow_ids_denied": self.flow_summary.flow_ids_denied,
                "flow_ids_error": self.flow_summary.flow_ids_error,
            },
            "errors": self.errors,
        }


class EmsConsumer:
    """Reference EMS consumer. Mirrors what EMS does after PR#127 merge."""

    def __init__(self, schema_path: Path | None = None) -> None:
        self._schema: dict | None = None
        if schema_path is None:
            # Default: relative to this file
            schema_path = Path(__file__).parent / "schema" / "ssid_runtime_report.schema.json"
        if schema_path.is_file():
            self._schema = json.loads(schema_path.read_text(encoding="utf-8"))

    # --- public interface ---

    def consume_file(self, report_path: Path | str) -> ConsumerResult:
        """Load a report from a JSON file and consume it."""
        path = Path(report_path)
        if not path.is_file():
            return self._error_result(
                f"Report file not found: {path}", CONTRACT_INCOMPLETE, EXIT_INCOMPLETE
            )
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            return self._error_result(
                f"Invalid JSON: {e}", CONTRACT_SCHEMA_MISMATCH, EXIT_INVALID_SCHEMA
            )
        return self.consume(report)

    def consume(self, report: dict[str, Any]) -> ConsumerResult:
        """Consume a report dict. Core classification logic."""
        errors: list[str] = []

        # Step 1: check required fields
        required = {"schema_version", "generated_at", "module_health", "flow_statuses"}
        missing = required - set(report.keys())
        if missing:
            return self._error_result(
                f"Missing required fields: {sorted(missing)}",
                CONTRACT_INCOMPLETE,
                EXIT_INCOMPLETE,
            )

        # Step 2: check schema_version compatibility
        schema_version = str(report.get("schema_version", ""))
        version_result = self._check_version(schema_version)
        if version_result is not None:
            return version_result

        # Step 3: validate against JSON Schema
        if _JSONSCHEMA_AVAILABLE and self._schema is not None:
            try:
                import jsonschema
                jsonschema.validate(report, self._schema)
            except jsonschema.ValidationError as e:
                return self._error_result(
                    f"Schema validation failed: {e.message}",
                    CONTRACT_SCHEMA_MISMATCH,
                    EXIT_INVALID_SCHEMA,
                )

        # Step 4: classify modules
        module_summary = self._classify_modules(report.get("module_health", []), errors)

        # Step 5: classify flows
        flow_summary = self._classify_flows(report.get("flow_statuses", []), errors)

        # Step 6: determine overall classification + exit code
        if flow_summary.denied > 0:
            overall = "denied"
            exit_code = EXIT_DENIED
        elif module_summary.offline > 0 or module_summary.degraded > 0 or flow_summary.error > 0 or flow_summary.degraded > 0:
            overall = "degraded"
            exit_code = EXIT_DEGRADED
        else:
            overall = "healthy"
            exit_code = EXIT_HEALTHY

        return ConsumerResult(
            exit_code=exit_code,
            contract_status=CONTRACT_VALID,
            overall_classification=overall,
            schema_version=schema_version,
            module_summary=module_summary,
            flow_summary=flow_summary,
            errors=errors,
        )

    # --- private helpers ---

    def _check_version(self, version: str) -> ConsumerResult | None:
        """Return error result if MAJOR version is incompatible, else None."""
        if not version:
            return self._error_result(
                "schema_version is empty", CONTRACT_VERSION_MISMATCH, EXIT_VERSION_MISMATCH
            )
        parts = version.split(".")
        if len(parts) != 3 or not all(p.isdigit() for p in parts):
            return self._error_result(
                f"schema_version '{version}' is not valid semver",
                CONTRACT_VERSION_MISMATCH,
                EXIT_VERSION_MISMATCH,
            )
        if parts[0] != EXPECTED_MAJOR:
            return self._error_result(
                f"MAJOR version mismatch: got {parts[0]}, expected {EXPECTED_MAJOR}",
                CONTRACT_VERSION_MISMATCH,
                EXIT_VERSION_MISMATCH,
            )
        return None

    def _classify_modules(
        self, module_health: list[dict], errors: list[str]
    ) -> ModuleSummary:
        healthy = degraded = offline = 0
        names_degraded: list[str] = []
        names_offline: list[str] = []
        for m in module_health:
            status = m.get("status", "")
            name = m.get("module_name", "?")
            if status == MODULE_STATUS_HEALTHY:
                healthy += 1
            elif status == MODULE_STATUS_DEGRADED:
                degraded += 1
                names_degraded.append(name)
            elif status == MODULE_STATUS_OFFLINE:
                offline += 1
                names_offline.append(name)
            else:
                errors.append(f"Unknown module status '{status}' for {name}")
        return ModuleSummary(
            total=len(module_health),
            healthy=healthy,
            degraded=degraded,
            offline=offline,
            names_degraded=names_degraded,
            names_offline=names_offline,
        )

    def _classify_flows(
        self, flow_statuses: list[dict], errors: list[str]
    ) -> FlowSummary:
        successful = denied = error = degraded = 0
        flow_ids_denied: list[str] = []
        flow_ids_error: list[str] = []
        for f in flow_statuses:
            status = f.get("status", "")
            fid = f.get("flow_id", f.get("flow_name", "?"))
            if status == FLOW_STATUS_SUCCESS:
                successful += 1
            elif status == FLOW_STATUS_DENIED:
                denied += 1
                flow_ids_denied.append(fid)
            elif status == FLOW_STATUS_ERROR:
                error += 1
                flow_ids_error.append(fid)
            elif status == FLOW_STATUS_DEGRADED:
                degraded += 1
            else:
                errors.append(f"Unknown flow status '{status}' for {fid}")
        return FlowSummary(
            total=len(flow_statuses),
            successful=successful,
            denied=denied,
            error=error,
            degraded=degraded,
            flow_ids_denied=flow_ids_denied,
            flow_ids_error=flow_ids_error,
        )

    @staticmethod
    def _error_result(
        message: str, contract_status: str, exit_code: int
    ) -> ConsumerResult:
        return ConsumerResult(
            exit_code=exit_code,
            contract_status=contract_status,
            overall_classification="error",
            schema_version="",
            module_summary=ModuleSummary(0, 0, 0, 0),
            flow_summary=FlowSummary(0, 0, 0, 0, 0),
            errors=[message],
        )


# CLI entrypoint
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python consumer_simulator.py <report.json>")
        sys.exit(5)
    consumer = EmsConsumer()
    result = consumer.consume_file(Path(sys.argv[1]))
    print(json.dumps(result.to_dict(), indent=2))
    sys.exit(result.exit_code)
