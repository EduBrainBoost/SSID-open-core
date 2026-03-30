import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


READY_STATE = "ready"
ALLOWED_RUNTIME_STATES = {"ready", "blocked", "degraded", "unknown"}
REGISTRY_PATH = Path("24_meta_orchestration/registry/shards_registry.json")


class RuntimeGateError(RuntimeError):
    """Base class for fail-closed runtime dependency gate errors."""

    def __init__(self, message: str, decision: "GateDecision") -> None:
        super().__init__(message)
        self.decision = decision


class RuntimeDependencyNotReadyError(RuntimeGateError):
    """Dependency or provider runtime state is not ready."""


class RuntimeCapabilityMissingError(RuntimeGateError):
    """Provider does not declare the requested dependency capability."""


class RuntimeContractMismatchError(RuntimeGateError):
    """Consumer contract reference does not match provider contract metadata."""


class RuntimeRegistryDriftError(RuntimeGateError):
    """Runtime/manifest/registry metadata is inconsistent."""


class RuntimeCanonicalConsumptionError(RuntimeGateError):
    """Consumer does not follow canonical consumption patterns (WAVE_06)."""


@dataclass(frozen=True)
class RuntimeDependency:
    consumer_root_id: str
    consumer_shard_id: str
    provider_root_id: str
    provider_shard_id: str
    dependency_capability: str
    dependency_status: str
    contract_ref: str | None = None


@dataclass(frozen=True)
class GateDecision:
    consumer_root_id: str
    consumer_shard_id: str
    provider_root_id: str
    provider_shard_id: str
    dependency_capability: str
    dependency_status: str
    service_runtime_status: str
    decision: str
    finding_code: str
    detail: str
    evidence_ref: str
    integrity_hash: str

    def to_event(self) -> dict[str, str]:
        return {
            "consumer_root_id": self.consumer_root_id,
            "consumer_shard_id": self.consumer_shard_id,
            "provider_root_id": self.provider_root_id,
            "provider_shard_id": self.provider_shard_id,
            "dependency_capability": self.dependency_capability,
            "dependency_status": self.dependency_status,
            "service_runtime_status": self.service_runtime_status,
            "decision": self.decision,
            "finding_code": self.finding_code,
            "detail": self.detail,
            "evidence_ref": self.evidence_ref,
            "integrity_hash": self.integrity_hash,
        }


@dataclass
class ShardRuntimeState:
    root_id: str
    shard_id: str
    chart_path: Path
    manifest_path: Path
    runtime_index_path: Path | None
    chart: dict[str, Any]
    manifest: dict[str, Any]
    runtime_index: dict[str, Any]
    capabilities: tuple[str, ...]
    provided_capabilities: tuple[str, ...]
    contracts: tuple[str, ...]
    service_runtime_status: str
    runtime_dependencies: tuple[RuntimeDependency, ...]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _json_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _normalize_shard_name(value: str) -> str:
    text = str(value or "").replace("\\", "/").strip("/")
    return text.split("/")[-1] if text else ""


def _normalize_contract_ref(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).replace("\\", "/").strip()
    return normalized or None


def _normalize_contract_set(values: list[Any] | tuple[Any, ...]) -> set[str]:
    result: set[str] = set()
    for item in values:
        if not item:
            continue
        normalized = _normalize_contract_ref(str(item))
        if normalized is None:
            continue
        result.add(normalized)
        result.add(Path(normalized).name)
    return result


def _collect_capabilities(chart: dict[str, Any], runtime_index: dict[str, Any]) -> tuple[str, ...]:
    caps: set[str] = set()
    chart_caps = chart.get("capabilities", {})
    if isinstance(chart_caps, dict):
        for bucket in ("must", "should", "could", "would"):
            values = chart_caps.get(bucket, [])
            if isinstance(values, list):
                for value in values:
                    if value:
                        caps.add(str(value))
    runtime_caps = runtime_index.get("provided_capabilities", [])
    if isinstance(runtime_caps, list):
        for value in runtime_caps:
            if value:
                caps.add(str(value))
    return tuple(sorted(caps))


def _collect_contracts(manifest: dict[str, Any], runtime_index: dict[str, Any]) -> tuple[str, ...]:
    values: list[str] = []
    for source in (manifest.get("contracts", []), runtime_index.get("contracts", [])):
        if isinstance(source, list):
            values.extend(str(item) for item in source if item)
    normalized = sorted(_normalize_contract_set(values))
    return tuple(normalized)


def _dependency_from_mapping(consumer_root_id: str, consumer_shard_id: str, payload: dict[str, Any]) -> RuntimeDependency:
    return RuntimeDependency(
        consumer_root_id=consumer_root_id,
        consumer_shard_id=consumer_shard_id,
        provider_root_id=str(payload.get("provider_root_id", "")),
        provider_shard_id=_normalize_shard_name(payload.get("provider_shard_id", "")),
        dependency_capability=str(payload.get("dependency_capability", "")),
        dependency_status=str(payload.get("dependency_status", "unknown")),
        contract_ref=_normalize_contract_ref(payload.get("contract_ref")),
    )


def _collect_runtime_dependencies(root_id: str, shard_id: str, manifest: dict[str, Any], runtime_index: dict[str, Any]) -> tuple[RuntimeDependency, ...]:
    payload = manifest.get("runtime_dependencies")
    if payload is None:
        payload = runtime_index.get("runtime_dependencies", [])
    if not isinstance(payload, list):
        return ()
    dependencies = [
        _dependency_from_mapping(root_id, shard_id, item)
        for item in payload
        if isinstance(item, dict)
    ]
    return tuple(dependencies)


def load_shard_state(repo_root: Path, root_id: str, shard_id: str) -> ShardRuntimeState:
    base = repo_root / root_id / "shards" / shard_id
    chart_path = base / "chart.yaml"
    manifest_path = base / "manifest.yaml"
    runtime_index_path = base / "runtime" / "index.yaml"

    chart = _read_yaml(chart_path)
    manifest = _read_yaml(manifest_path)
    runtime_index = _read_yaml(runtime_index_path)
    runtime_path = runtime_index_path if runtime_index_path.exists() else None

    service_runtime_status = str(
        runtime_index.get("service_runtime_status")
        or manifest.get("service_runtime_status")
        or "unknown"
    )
    capabilities = _collect_capabilities(chart, runtime_index)
    dependencies = _collect_runtime_dependencies(root_id, shard_id, manifest, runtime_index)

    return ShardRuntimeState(
        root_id=root_id,
        shard_id=shard_id,
        chart_path=chart_path,
        manifest_path=manifest_path,
        runtime_index_path=runtime_path,
        chart=chart,
        manifest=manifest,
        runtime_index=runtime_index,
        capabilities=capabilities,
        provided_capabilities=capabilities,
        contracts=_collect_contracts(manifest, runtime_index),
        service_runtime_status=service_runtime_status,
        runtime_dependencies=dependencies,
    )


def collect_runtime_dependencies(repo_root: Path, consumer_root_id: str, consumer_shard_id: str) -> list[RuntimeDependency]:
    state = load_shard_state(repo_root, consumer_root_id, consumer_shard_id)
    return list(state.runtime_dependencies)


def derive_registry_runtime_fields(state: ShardRuntimeState) -> dict[str, Any]:
    dependency_capability = sorted({dep.dependency_capability for dep in state.runtime_dependencies if dep.dependency_capability})
    dependency_status = "n/a"
    if state.runtime_dependencies:
        dependency_status = "ready" if all(dep.dependency_status == READY_STATE for dep in state.runtime_dependencies) else "blocked"
    runtime_index_path = None
    if state.runtime_index_path is not None:
        runtime_index_path = f"{state.root_id}/shards/{state.shard_id}/runtime/index.yaml"
    return {
        "service_runtime_status": state.service_runtime_status,
        "dependency_capability": dependency_capability,
        "dependency_status": dependency_status,
        "provided_capabilities": list(state.provided_capabilities),
        "runtime_index_path": runtime_index_path,
    }


def _load_registry_map(repo_root: Path) -> dict[tuple[str, str], dict[str, Any]]:
    registry_path = repo_root / REGISTRY_PATH
    if not registry_path.exists():
        return {}
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    shards = payload.get("shards", [])
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for item in shards:
        if not isinstance(item, dict):
            continue
        result[(str(item.get("root_id", "")), _normalize_shard_name(item.get("shard_id", "")))] = item
    return result


def _build_decision(
    dependency: RuntimeDependency,
    *,
    decision: str,
    finding_code: str,
    detail: str,
    service_runtime_status: str,
) -> GateDecision:
    event = {
        "consumer_root_id": dependency.consumer_root_id,
        "consumer_shard_id": dependency.consumer_shard_id,
        "provider_root_id": dependency.provider_root_id,
        "provider_shard_id": dependency.provider_shard_id,
        "dependency_capability": dependency.dependency_capability,
        "dependency_status": dependency.dependency_status,
        "service_runtime_status": service_runtime_status,
        "decision": decision,
        "finding_code": finding_code,
        "detail": detail,
        "evidence_ref": (
            f"runtime-gate:{dependency.consumer_root_id}/{dependency.consumer_shard_id}:"
            f"{dependency.provider_root_id}/{dependency.provider_shard_id}:{dependency.dependency_capability}"
        ),
    }
    event["integrity_hash"] = _json_hash(event)
    return GateDecision(**event)


def _raise(error_cls: type[RuntimeGateError], dependency: RuntimeDependency, finding_code: str, detail: str, service_runtime_status: str) -> None:
    decision = _build_decision(
        dependency,
        decision="block",
        finding_code=finding_code,
        detail=detail,
        service_runtime_status=service_runtime_status,
    )
    raise error_cls(detail, decision)


def _assert_runtime_state_valid(state: ShardRuntimeState, dependency: RuntimeDependency) -> None:
    manifest_status = state.manifest.get("service_runtime_status")
    runtime_status = state.runtime_index.get("service_runtime_status")
    if manifest_status and runtime_status and manifest_status != runtime_status:
        _raise(
            RuntimeRegistryDriftError,
            dependency,
            "runtime_manifest_drift",
            f"{state.root_id}/{state.shard_id} manifest/runtime status drift: {manifest_status} != {runtime_status}",
            state.service_runtime_status,
        )
    if state.service_runtime_status not in ALLOWED_RUNTIME_STATES:
        _raise(
            RuntimeRegistryDriftError,
            dependency,
            "runtime_status_invalid",
            f"{state.root_id}/{state.shard_id} has invalid service_runtime_status={state.service_runtime_status}",
            state.service_runtime_status,
        )


def _assert_registry_consistent(repo_root: Path, state: ShardRuntimeState, dependency: RuntimeDependency) -> None:
    registry = _load_registry_map(repo_root)
    entry = registry.get((state.root_id, state.shard_id))
    if entry is None:
        _raise(
            RuntimeRegistryDriftError,
            dependency,
            "runtime_registry_missing",
            f"Registry entry missing for {state.root_id}/{state.shard_id}",
            state.service_runtime_status,
        )

    expected = derive_registry_runtime_fields(state)
    for key, expected_value in expected.items():
        actual_value = entry.get(key)
        if actual_value != expected_value:
            _raise(
                RuntimeRegistryDriftError,
                dependency,
                "runtime_registry_drift",
                (
                    f"Registry drift for {state.root_id}/{state.shard_id}: {key}="
                    f"{actual_value!r} expected {expected_value!r}"
                ),
                state.service_runtime_status,
            )


def evaluate_runtime_dependency(repo_root: Path, dependency: RuntimeDependency) -> GateDecision:
    consumer_state = load_shard_state(repo_root, dependency.consumer_root_id, dependency.consumer_shard_id)
    provider_state = load_shard_state(repo_root, dependency.provider_root_id, dependency.provider_shard_id)

    _assert_runtime_state_valid(consumer_state, dependency)
    _assert_runtime_state_valid(provider_state, dependency)
    _assert_registry_consistent(repo_root, consumer_state, dependency)
    _assert_registry_consistent(repo_root, provider_state, dependency)

    if dependency.dependency_status != READY_STATE:
        _raise(
            RuntimeDependencyNotReadyError,
            dependency,
            "runtime_dependency_not_ready",
            (
                f"{dependency.consumer_root_id}/{dependency.consumer_shard_id} declares "
                f"{dependency.provider_root_id}/{dependency.provider_shard_id} as {dependency.dependency_status}"
            ),
            provider_state.service_runtime_status,
        )

    if provider_state.service_runtime_status != READY_STATE:
        _raise(
            RuntimeDependencyNotReadyError,
            dependency,
            "runtime_provider_not_ready",
            (
                f"{dependency.provider_root_id}/{dependency.provider_shard_id} service_runtime_status="
                f"{provider_state.service_runtime_status}"
            ),
            provider_state.service_runtime_status,
        )

    if dependency.dependency_capability not in provider_state.provided_capabilities:
        _raise(
            RuntimeCapabilityMissingError,
            dependency,
            "runtime_capability_missing",
            (
                f"{dependency.provider_root_id}/{dependency.provider_shard_id} does not provide "
                f"{dependency.dependency_capability}"
            ),
            provider_state.service_runtime_status,
        )

    normalized_contract = _normalize_contract_ref(dependency.contract_ref)
    if normalized_contract:
        provider_contracts = set(provider_state.contracts)
        if normalized_contract not in provider_contracts and Path(normalized_contract).name not in provider_contracts:
            _raise(
                RuntimeContractMismatchError,
                dependency,
                "runtime_contract_mismatch",
                (
                    f"{dependency.provider_root_id}/{dependency.provider_shard_id} contracts "
                    f"do not include {normalized_contract}"
                ),
                provider_state.service_runtime_status,
            )

    return _build_decision(
        dependency,
        decision="allow",
        finding_code="runtime_dependency_ready",
        detail=(
            f"{dependency.consumer_root_id}/{dependency.consumer_shard_id} may use "
            f"{dependency.provider_root_id}/{dependency.provider_shard_id}:{dependency.dependency_capability}"
        ),
        service_runtime_status=provider_state.service_runtime_status,
    )


def append_gate_decisions(decision_log_path: Path, decisions: list[GateDecision]) -> None:
    decision_log_path.parent.mkdir(parents=True, exist_ok=True)
    with decision_log_path.open("a", encoding="utf-8") as handle:
        for decision in decisions:
            event = {
                "event_id": f"RTG-{decision.integrity_hash[:12].upper()}",
                "timestamp_utc": _utc_now(),
                "root": decision.consumer_root_id,
                "shard": decision.consumer_shard_id,
                "actor_ref_hash": hashlib.sha256(
                    f"{decision.consumer_root_id}/{decision.consumer_shard_id}".encode("utf-8")
                ).hexdigest(),
                "action": "cross_root_runtime_gate",
                "result": decision.decision.upper(),
                "evidence_ref": decision.evidence_ref,
                "integrity_hash": decision.integrity_hash,
                "finding_code": decision.finding_code,
                "provider_root_id": decision.provider_root_id,
                "provider_shard_id": decision.provider_shard_id,
                "dependency_capability": decision.dependency_capability,
                "detail": decision.detail,
            }
            handle.write(json.dumps(event, sort_keys=True, ensure_ascii=False) + "\n")


def enforce_runtime_dependencies(
    repo_root: Path,
    consumer_root_id: str,
    consumer_shard_id: str,
    *,
    decision_log_path: Path | None = None,
) -> list[GateDecision]:
    decisions: list[GateDecision] = []
    dependencies = collect_runtime_dependencies(repo_root, consumer_root_id, consumer_shard_id)
    for dependency in dependencies:
        try:
            decisions.append(evaluate_runtime_dependency(repo_root, dependency))
        except RuntimeGateError as exc:
            blocked = decisions + [exc.decision]
            if decision_log_path is not None:
                append_gate_decisions(decision_log_path, blocked)
            raise

    if decision_log_path is not None and decisions:
        append_gate_decisions(decision_log_path, decisions)
    return decisions
