"""Evidence logging with SHA-256 integrity for brain console interactions."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class EvidenceEntry:
    """Immutable evidence record for a single brain console interaction."""

    entry_id: str = field(default_factory=lambda: f"ev_{uuid.uuid4().hex[:16]}")
    timestamp: str = field(
        default_factory=lambda: dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )
    sha256: str = ""
    payload_ref: str = ""
    session_id: str = ""
    message_id: str = ""
    role: str = ""
    query_hash: str = ""
    response_hash: str = ""
    policy_decision: str = ""
    context_summary: dict[str, Any] = field(default_factory=dict)
    evidence_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return asdict(self)


def _sha256(text: str) -> str:
    """Compute SHA-256 hex digest of a UTF-8 string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class BrainEvidenceLogger:
    """Writes evidence entries with SHA-256 integrity.

    Parameters
    ----------
    evidence_root : Path or str, optional
        Directory where evidence JSON files are written.
        If None, operates in memory-only mode.
    """

    def __init__(self, evidence_root: Path | None = None) -> None:
        self._root = Path(evidence_root) if evidence_root else None
        if self._root is not None:
            self._root.mkdir(parents=True, exist_ok=True)

    def log_interaction(
        self,
        session_id: str,
        message_id: str,
        role: str,
        query: str,
        response: str,
        policy_decision: str,
        context_summary: dict[str, Any] | None = None,
    ) -> EvidenceEntry:
        """Create and persist an evidence entry for a brain console interaction.

        Query and response are stored as SHA-256 hashes only (no plaintext).
        """
        query_hash = _sha256(query)
        response_hash = _sha256(response)

        # Build the payload for integrity hashing
        payload = {
            "session_id": session_id,
            "message_id": message_id,
            "role": role,
            "query_hash": query_hash,
            "response_hash": response_hash,
            "policy_decision": policy_decision,
            "context_summary": context_summary or {},
        }
        payload_json = json.dumps(payload, sort_keys=True)
        evidence_hash = _sha256(payload_json)

        entry = EvidenceEntry(
            session_id=session_id,
            message_id=message_id,
            role=role,
            query_hash=query_hash,
            response_hash=response_hash,
            policy_decision=policy_decision,
            context_summary=context_summary or {},
            sha256=evidence_hash,
            payload_ref=f"evidence/{session_id}/{message_id}.json",
            evidence_hash=evidence_hash,
        )

        # Persist to disk if root is configured
        if self._root is not None:
            session_dir = self._root / session_id
            session_dir.mkdir(parents=True, exist_ok=True)
            evidence_file = session_dir / f"{message_id}.json"
            evidence_file.write_text(
                json.dumps(entry.to_dict(), indent=2, sort_keys=True),
                encoding="utf-8",
            )

        return entry
