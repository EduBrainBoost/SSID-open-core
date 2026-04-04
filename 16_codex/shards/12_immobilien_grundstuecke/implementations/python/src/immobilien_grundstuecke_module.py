"""Codex module for Immobilien und Grundstuecke — Knowledge Indexer."""

import hashlib
import json
from datetime import UTC, datetime


class KnowledgeIndexer:
    """Knowledge indexer for Immobilien und Grundstuecke in the Codex."""

    def __init__(self):
        self._index = {}
        self._evidence_log = []

    def index_entry(self, entry_id: str, content: dict) -> dict:
        content_hash = hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()
        record = {
            "entry_id_hash": hashlib.sha256(entry_id.encode()).hexdigest(),
            "content_hash": content_hash,
            "indexed_at": datetime.now(UTC).isoformat(),
            "domain": "immobilien_grundstuecke",
            "non_custodial": True,
        }
        self._index[content_hash] = record
        self._evidence_log.append(record)
        return record

    def search(self, query: str) -> list:
        query_hash = hashlib.sha256(query.encode()).hexdigest()
        results = [v for k, v in self._index.items() if query_hash[:8] in k]
        return results

    def validate_schema(self, schema: dict, data: dict) -> dict:
        schema_hash = hashlib.sha256(json.dumps(schema, sort_keys=True).encode()).hexdigest()
        data_hash = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
        return {
            "schema_hash": schema_hash,
            "data_hash": data_hash,
            "valid": isinstance(data, dict),
            "validated_at": datetime.now(UTC).isoformat(),
            "non_custodial": True,
        }
