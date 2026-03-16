from __future__ import annotations

from pathlib import Path
from typing import Any

from reference_security import (
    SecurityEnforcementBridge,
    SecurityPolicyDeniedError,
    SecurityRuntimeDependencyError,
    SecurityEvidence,
)


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


class Root07SecurityEnforcementWave:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.root_dir = repo_root / "07_governance_legal" / "shards"

    def _resolve(self, shard_id: str) -> str:
        return SHARD_ALIASES.get(shard_id, shard_id)

    def dependency_refs_for(self, shard_id: str) -> list[str]:
        resolved = self._resolve(shard_id)
        return [f"03_core/{resolved}", f"09_meta_identity/{resolved}"]

    def _assert_dependencies_ready(self, resolved_shard_id: str) -> None:
        for dependency_ref in self.dependency_refs_for(resolved_shard_id):
            root_id, shard_name = dependency_ref.split("/", 1)
            runtime_index = self.repo_root / root_id / "shards" / shard_name / "runtime" / "index.yaml"
            if not runtime_index.is_file():
                raise SecurityRuntimeDependencyError(f"missing runtime dependency: {dependency_ref}")

    def bridge_for(self, shard_id: str) -> SecurityEnforcementBridge:
        resolved = self._resolve(shard_id)
        self._assert_dependencies_ready(resolved)
        return SecurityEnforcementBridge(self.root_dir / resolved, self.dependency_refs_for(resolved))

    def run(self, shard_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any], SecurityEvidence]:
        resolved = self._resolve(shard_id)
        self._assert_dependencies_ready(resolved)
        return self.bridge_for(resolved).enforce(payload)


__all__ = [
    "Root07SecurityEnforcementWave",
    "SecurityPolicyDeniedError",
    "SecurityRuntimeDependencyError",
]
