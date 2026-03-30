"""Brain Context Assembly — collects context from Session, Memory, and Evidence."""
from __future__ import annotations

import datetime as dt
import hashlib
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class BrainContext:
    """Immutable snapshot of assembled brain context for a single interaction."""

    session_id: str
    memory_snapshot: Dict[str, Any] = field(default_factory=dict)
    evidence_refs: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: (
        dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        .isoformat().replace("+00:00", "Z")
    ))
    role: str = "user"
    sot_available: bool = False
    registry_available: bool = False
    evidence_available: bool = False
    allowed_topics: List[str] = field(default_factory=list)
    query_hash: str = ""
    blocked: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return asdict(self)


class BrainContextAssembler:
    """Assembles a BrainContext from session, memory, and evidence sources.

    Parameters
    ----------
    repo_root : Path or str, optional
        Root of the SSID repository. Used to locate SoT/registry data.
    """

    # Role-based scope definitions (mirrors EMS ROLE_SCOPE)
    _ROLE_SCOPE = {
        "user": {
            "allowed_topics": ["product", "identity", "wallet", "flow", "general"],
            "sot_access": True,
            "registry_access": False,
            "evidence_access": False,
        },
        "partner": {
            "allowed_topics": ["integration", "registry", "api", "compliance", "product"],
            "sot_access": True,
            "registry_access": True,
            "evidence_access": False,
        },
        "auditor": {
            "allowed_topics": ["policy", "evidence", "compliance", "run", "audit"],
            "sot_access": True,
            "registry_access": True,
            "evidence_access": True,
        },
        "operator": {
            "allowed_topics": ["*"],
            "sot_access": True,
            "registry_access": True,
            "evidence_access": True,
        },
        "demo": {
            "allowed_topics": ["product", "identity", "wallet", "general", "demo"],
            "sot_access": True,
            "registry_access": False,
            "evidence_access": False,
        },
    }

    _CANONICAL_FORBIDDEN = ["documents/github"]

    def __init__(self, repo_root: Optional[Path] = None) -> None:
        self._repo_root = Path(repo_root) if repo_root else None

    def assemble(
        self,
        role: str,
        session_id: str,
        query: str,
    ) -> BrainContext:
        """Assemble a BrainContext for the given role/session/query.

        Returns a BrainContext with scope-appropriate fields populated.
        Blocks queries referencing canonical zones.
        """
        scope = self._ROLE_SCOPE.get(role, self._ROLE_SCOPE["user"])
        query_hash = hashlib.sha256(query.encode("utf-8")).hexdigest()

        # Canonical zone check
        query_lower = query.lower()
        for marker in self._CANONICAL_FORBIDDEN:
            if marker in query_lower:
                return BrainContext(
                    session_id=session_id,
                    role=role,
                    query_hash=query_hash,
                    blocked=True,
                )

        return BrainContext(
            session_id=session_id,
            role=role,
            sot_available=scope["sot_access"],
            registry_available=scope["registry_access"],
            evidence_available=scope["evidence_access"],
            allowed_topics=list(scope["allowed_topics"]),
            query_hash=query_hash,
        )
