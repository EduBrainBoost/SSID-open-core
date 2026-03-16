from __future__ import annotations

from pathlib import Path
from typing import Any

from reference_runtime import (
    ClaimsBindingProcessor,
    ContractBoundProcessor,
    CredentialProcessor,
    DidResolutionProcessor,
    DocumentProcessor,
    IdentityProcessor,
    OperationEvidence,
    Root03Service,
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

PROCESSOR_BY_SHARD = {
    "01_identitaet_personen": IdentityProcessor,
    "02_dokumente_nachweise": DocumentProcessor,
    "03_shard_03": CredentialProcessor,
    "04_shard_04": DidResolutionProcessor,
    "05_shard_05": ClaimsBindingProcessor,
}


class Root03ReferenceWave:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.root_dir = repo_root / "03_core" / "shards"

    def available_shards(self) -> list[str]:
        return [name for name in PRIORITY_SHARDS if (self.root_dir / name).is_dir()]

    def processor_for(self, shard_id: str) -> ContractBoundProcessor:
        resolved = SHARD_ALIASES.get(shard_id, shard_id)
        processor_cls = PROCESSOR_BY_SHARD.get(resolved, ContractBoundProcessor)
        return processor_cls(self.root_dir / resolved)

    def service_for(self, shard_id: str) -> Root03Service:
        return Root03Service(self.processor_for(shard_id))

    def run(self, shard_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any], OperationEvidence]:
        return self.processor_for(shard_id).process(payload)
