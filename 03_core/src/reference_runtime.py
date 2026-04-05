from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jsonschema


class ReferenceRuntimeError(Exception):
    pass


class ContractValidationError(ReferenceRuntimeError):
    pass


class ProcessingError(ReferenceRuntimeError):
    pass


class SerializationError(ReferenceRuntimeError):
    pass


@dataclass(frozen=True)
class OperationEvidence:
    shard_id: str
    operation: str
    input_sha256: str
    output_sha256: str
    audit_event: str


def _sha256_payload(payload: dict[str, Any]) -> str:
    rendered = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(rendered).hexdigest()


def serialize_payload(payload: dict[str, Any]) -> str:
    try:
        return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    except TypeError as exc:
        raise SerializationError(str(exc)) from exc


class ContractBoundProcessor:
    def __init__(self, shard_dir: Path):
        self.shard_dir = shard_dir
        self.contracts_dir = shard_dir / "contracts"
        self.evidence_dir = shard_dir / "evidence"
        self.inputs_schema = self._load_schema("inputs.schema.json")
        self.outputs_schema = self._load_schema("outputs.schema.json")

    def _load_schema(self, filename: str) -> dict[str, Any]:
        path = self.contracts_dir / filename
        if not path.is_file():
            raise ContractValidationError(f"missing schema: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def validate_input(self, payload: dict[str, Any]) -> None:
        try:
            jsonschema.validate(payload, self.inputs_schema)
        except jsonschema.ValidationError as exc:
            raise ContractValidationError(str(exc)) from exc

    def validate_output(self, payload: dict[str, Any]) -> None:
        try:
            jsonschema.validate(payload, self.outputs_schema)
        except jsonschema.ValidationError as exc:
            raise ContractValidationError(str(exc)) from exc

    def _write_audit_event(self, payload: dict[str, Any], result: dict[str, Any]) -> str:
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        event = {
            "shard_id": self.shard_dir.name,
            "operation": "process",
            "input_sha256": _sha256_payload(payload),
            "output_sha256": _sha256_payload(result),
        }
        event_path = self.evidence_dir / "runtime_audit.jsonl"
        with event_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        return event_path.as_posix()

    def build_result(self, payload: dict[str, Any]) -> dict[str, Any]:
        if "payload_hash" not in payload:
            raise ProcessingError("payload_hash required")
        return {
            "result_id": payload["request_id"],
            "status": "accepted",
        }

    def process(self, payload: dict[str, Any]) -> tuple[dict[str, Any], OperationEvidence]:
        self.validate_input(payload)
        serialize_payload(payload)
        result = self.build_result(payload)
        self.validate_output(result)
        serialize_payload(result)
        audit_event = self._write_audit_event(payload, result)
        evidence = OperationEvidence(
            shard_id=self.shard_dir.name,
            operation="process",
            input_sha256=_sha256_payload(payload),
            output_sha256=_sha256_payload(result),
            audit_event=audit_event,
        )
        return result, evidence


class IdentityProcessor(ContractBoundProcessor):
    def build_result(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = super().build_result(payload)
        result["status"] = "accepted"
        return result


class DocumentProcessor(ContractBoundProcessor):
    def build_result(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = super().build_result(payload)
        result["status"] = "accepted"
        return result


class CredentialProcessor(ContractBoundProcessor):
    def build_result(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = super().build_result(payload)
        result["status"] = "accepted"
        return result


class DidResolutionProcessor(ContractBoundProcessor):
    def build_result(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = super().build_result(payload)
        result["status"] = "accepted"
        return result


class ClaimsBindingProcessor(ContractBoundProcessor):
    def build_result(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = super().build_result(payload)
        result["status"] = "accepted"
        return result


class Root03Service:
    def __init__(self, processor: ContractBoundProcessor):
        self.processor = processor

    def execute(self, payload: dict[str, Any]) -> tuple[str, OperationEvidence]:
        result, evidence = self.processor.process(payload)
        return serialize_payload(result), evidence
