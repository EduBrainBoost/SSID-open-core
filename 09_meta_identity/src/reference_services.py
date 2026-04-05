from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jsonschema


class ReferenceServiceError(Exception):
    pass


class ServiceContractError(ReferenceServiceError):
    pass


class ServiceDependencyError(ReferenceServiceError):
    pass


class ServiceSerializationError(ReferenceServiceError):
    pass


@dataclass(frozen=True)
class ServiceEvidence:
    root_id: str
    shard_id: str
    operation: str
    input_sha256: str
    output_sha256: str
    dependency_refs: list[str]
    audit_event: str


def _sha256_payload(payload: dict[str, Any]) -> str:
    rendered = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(rendered).hexdigest()


def serialize_payload(payload: dict[str, Any]) -> str:
    try:
        return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    except TypeError as exc:
        raise ServiceSerializationError(str(exc)) from exc


class ContractBoundServiceProcessor:
    def __init__(self, shard_dir: Path, dependency_refs: list[str]):
        self.shard_dir = shard_dir
        self.contracts_dir = shard_dir / "contracts"
        self.evidence_dir = shard_dir / "evidence"
        self.dependency_refs = dependency_refs
        self.inputs_schema = self._load_schema("inputs.schema.json")
        self.outputs_schema = self._load_schema("outputs.schema.json")

    def _load_schema(self, filename: str) -> dict[str, Any]:
        path = self.contracts_dir / filename
        if not path.is_file():
            raise ServiceContractError(f"missing schema: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def validate_input(self, payload: dict[str, Any]) -> None:
        try:
            jsonschema.validate(payload, self.inputs_schema)
        except jsonschema.ValidationError as exc:
            raise ServiceContractError(str(exc)) from exc

    def validate_output(self, payload: dict[str, Any]) -> None:
        try:
            jsonschema.validate(payload, self.outputs_schema)
        except jsonschema.ValidationError as exc:
            raise ServiceContractError(str(exc)) from exc

    def _write_audit_event(self, payload: dict[str, Any], result: dict[str, Any]) -> str:
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        event = {
            "root_id": "09_meta_identity",
            "shard_id": self.shard_dir.name,
            "operation": "service_execute",
            "dependency_refs": self.dependency_refs,
            "input_sha256": _sha256_payload(payload),
            "output_sha256": _sha256_payload(result),
        }
        event_path = self.evidence_dir / "service_runtime_audit.jsonl"
        with event_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        return event_path.as_posix()

    def build_result(self, payload: dict[str, Any], core_result: dict[str, Any]) -> dict[str, Any]:
        if core_result.get("status") != "accepted":
            raise ServiceDependencyError("core dependency returned non-accepted status")
        return {
            "result_id": payload["request_id"],
            "status": "accepted",
        }

    def process(self, payload: dict[str, Any], core_result: dict[str, Any]) -> tuple[dict[str, Any], ServiceEvidence]:
        self.validate_input(payload)
        serialize_payload(payload)
        result = self.build_result(payload, core_result)
        self.validate_output(result)
        serialize_payload(result)
        audit_event = self._write_audit_event(payload, result)
        evidence = ServiceEvidence(
            root_id="09_meta_identity",
            shard_id=self.shard_dir.name,
            operation="service_execute",
            input_sha256=_sha256_payload(payload),
            output_sha256=_sha256_payload(result),
            dependency_refs=self.dependency_refs,
            audit_event=audit_event,
        )
        return result, evidence

