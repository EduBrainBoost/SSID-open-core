from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from reference_runtime import ContractValidationError
from reference_services import (
    ContractBoundServiceProcessor,
    ServiceContractError,
    ServiceDependencyError,
    ServiceEvidence,
)
from wave03_reference import Root03ReferenceWave

PRIORITY_SHARDS = [
    "01_identitaet_personen",
    "02_dokumente_nachweise",
    "03_shard_03",
    "04_shard_04",
    "05_shard_05",
]

SHARD_ALIASES = {
    "03_verifiable_credentials": "03_shard_03",
    "04_did_resolution": "04_shard_04",
    "05_claims_binding": "05_shard_05",
}

CORE_DEPENDENCIES = {
    "01_identitaet_personen": "03_core/01_identitaet_personen",
    "02_dokumente_nachweise": "03_core/02_dokumente_nachweise",
    "03_shard_03": "03_core/03_shard_03",
    "04_shard_04": "03_core/04_shard_04",
    "05_shard_05": "03_core/05_shard_05",
}


class Root09IdentityServicesWave:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.root_dir = repo_root / "09_meta_identity" / "shards"
        self.core_wave = Root03ReferenceWave(repo_root)

    def available_shards(self) -> list[str]:
        return [name for name in PRIORITY_SHARDS if (self.root_dir / name).is_dir()]

    def _resolve(self, shard_id: str) -> str:
        return SHARD_ALIASES.get(shard_id, shard_id)

    def dependency_refs_for(self, shard_id: str) -> list[str]:
        resolved = self._resolve(shard_id)
        dependency = CORE_DEPENDENCIES.get(resolved)
        return [dependency] if dependency else []

    def _assert_dependency_ready(self, resolved_shard_id: str) -> None:
        dependency_ref = CORE_DEPENDENCIES.get(resolved_shard_id)
        if not dependency_ref:
            raise ServiceDependencyError(f"missing core runtime dependency mapping for {resolved_shard_id}")
        root_id, shard_name = dependency_ref.split("/", 1)
        runtime_index = self.repo_root / root_id / "shards" / shard_name / "runtime" / "index.yaml"
        if not runtime_index.is_file():
            raise ServiceDependencyError(f"missing core runtime dependency: {dependency_ref}")

    def processor_for(self, shard_id: str) -> ContractBoundServiceProcessor:
        resolved = self._resolve(shard_id)
        self._assert_dependency_ready(resolved)
        return ContractBoundServiceProcessor(self.root_dir / resolved, self.dependency_refs_for(resolved))

    def run(self, shard_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any], ServiceEvidence]:
        resolved = self._resolve(shard_id)
        self._assert_dependency_ready(resolved)
        _, dependency_shard = CORE_DEPENDENCIES[resolved].split("/", 1)
        try:
            core_result, _ = self.core_wave.run(dependency_shard, payload)
        except ContractValidationError as exc:
            raise ServiceContractError(str(exc)) from exc
        return self.processor_for(resolved).process(payload, core_result)


def load_runtime_spec(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
