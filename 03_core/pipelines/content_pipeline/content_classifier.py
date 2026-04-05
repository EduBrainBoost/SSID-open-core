"""content_classifier.py — Rule-based classification of extracted content.

Compute-only: classifies ExtractedContent into one or more categories with a
per-category confidence score.  No ML models; purely keyword + path heuristics.

No PII is handled; output is deterministic given identical inputs.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .content_extractor import ExtractedContent

# ---------------------------------------------------------------------------
# Category vocabulary
# ---------------------------------------------------------------------------

CATEGORIES = (
    "architecture",
    "governance",
    "compliance",
    "technical",
    "knowledge",
    "policy",
    "contract",
)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CategoryScore:
    """Confidence score for a single category."""

    category: str
    score: float  # 0.0 – 1.0
    matched_signals: tuple[str, ...]  # human-readable explanation


@dataclass(frozen=True)
class Classification:
    """Full classification result for one piece of content."""

    primary_category: str
    all_scores: tuple[CategoryScore, ...]
    input_hash: str  # SHA-256 of (source_path + body)
    evidence_hash: str  # SHA-256 of full classification output


# ---------------------------------------------------------------------------
# Signal tables
# ---------------------------------------------------------------------------

# Each entry: (regex_pattern, signal_label, weight)
_KEYWORD_SIGNALS: dict[str, list[tuple[str, str, float]]] = {
    "architecture": [
        (r"\barchitecture\b", "keyword:architecture", 0.4),
        (r"\bADR\b", "keyword:ADR", 0.35),
        (r"\bdesign\b", "keyword:design", 0.15),
        (r"\bcomponent\b|\bmodule\b", "keyword:component-module", 0.1),
        (r"\bsystem\b", "keyword:system", 0.05),
        (r"\bdiagram\b|\bblueprint\b", "keyword:diagram", 0.1),
    ],
    "governance": [
        (r"\bgovernance\b", "keyword:governance", 0.45),
        (r"\bdecision\b", "keyword:decision", 0.25),
        (r"\bpolicy\b", "keyword:policy", 0.1),
        (r"\blifecycle\b", "keyword:lifecycle", 0.1),
        (r"\bapproval\b|\bsign-?off\b", "keyword:approval", 0.15),
        (r"\bcommittee\b|\bboard\b", "keyword:committee", 0.1),
    ],
    "compliance": [
        (r"\bcompliance\b", "keyword:compliance", 0.45),
        (r"\baudit\b", "keyword:audit", 0.3),
        (r"\bregulat\w*\b", "keyword:regulatory", 0.25),
        (r"\bGDPR\b|\bDSGVO\b", "keyword:GDPR", 0.3),
        (r"\bevidence\b", "keyword:evidence", 0.15),
        (r"\bcertif\w*\b", "keyword:certification", 0.15),
    ],
    "technical": [
        (r"\bAPI\b|\bREST\b|\bHTTP\b", "keyword:api-rest", 0.3),
        (r"\bimplementation\b", "keyword:implementation", 0.25),
        (r"\bcode\b|\bfunction\b|\bclass\b", "keyword:code", 0.2),
        (r"\bpackage\b|\bmodule\b", "keyword:package-module", 0.15),
        (r"\bdeploy\w*\b", "keyword:deploy", 0.15),
        (r"\bdocker\b|\bkubernetes\b|\bcontainer\b", "keyword:infra", 0.25),
        (r"\btest\w*\b|\bCI\b|\bCD\b", "keyword:testing-ci", 0.1),
    ],
    "knowledge": [
        (r"\bknowledge\b", "keyword:knowledge", 0.35),
        (r"\bdocumentation\b|\bdocs\b", "keyword:docs", 0.3),
        (r"\bcodex\b", "keyword:codex", 0.35),
        (r"\bguide\b|\btutorial\b|\bhowto\b", "keyword:guide", 0.2),
        (r"\bshard\b", "keyword:shard", 0.15),
        (r"\blesson\b|\bpostmortem\b", "keyword:postmortem", 0.2),
    ],
    "policy": [
        (r"\bpolicy\b", "keyword:policy", 0.4),
        (r"\brego\b|\bopen\s*policy\b", "keyword:rego-opa", 0.4),
        (r"\brule\b|\bconstraint\b", "keyword:rule", 0.2),
        (r"\ballow\b|\bdeny\b|\bforbid\b", "keyword:allow-deny", 0.2),
        (r"\bpermission\b|\bauthori[sz]ation\b", "keyword:authz", 0.15),
    ],
    "contract": [
        (r"\bcontract\b", "keyword:contract", 0.45),
        (r"\bagreement\b", "keyword:agreement", 0.35),
        (r"\bSLA\b|\bSLO\b", "keyword:SLA", 0.3),
        (r"\bobligation\b|\bliability\b", "keyword:obligation", 0.25),
        (r"\bparty\b|\bparties\b", "keyword:parties", 0.15),
        (r"\bterms\b|\bconditions\b", "keyword:terms", 0.1),
    ],
}

# Path-based signals: (path_segment, category, weight)
_PATH_SIGNALS: list[tuple[str, str, float]] = [
    ("decisions", "governance", 0.5),
    ("adr", "architecture", 0.5),
    ("policies", "policy", 0.55),
    ("policy", "policy", 0.55),
    ("contracts", "contract", 0.55),
    ("contract", "contract", 0.55),
    ("docs", "knowledge", 0.3),
    ("documentation", "knowledge", 0.3),
    ("05_documentation", "knowledge", 0.4),
    ("16_codex", "knowledge", 0.45),
    ("codex", "knowledge", 0.4),
    ("shards", "knowledge", 0.25),
    ("03_core", "technical", 0.3),
    ("engines", "technical", 0.35),
    ("src", "technical", 0.2),
    ("compliance", "compliance", 0.55),
    ("audit", "compliance", 0.4),
    ("governance", "governance", 0.5),
    ("architecture", "architecture", 0.5),
]

# Content-type boosts
_TYPE_BOOSTS: dict[str, dict[str, float]] = {
    "policy": {"policy": 0.3},
    "yaml": {"technical": 0.05, "knowledge": 0.05},
    "json": {"technical": 0.1},
    "markdown": {"knowledge": 0.05},
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_dict(data: dict[str, Any]) -> str:
    s = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(s).hexdigest()


def _clamp(v: float) -> float:
    return max(0.0, min(1.0, v))


# ---------------------------------------------------------------------------
# ContentClassifier
# ---------------------------------------------------------------------------


class ContentClassifier:
    """
    Rule-based classifier for SSID knowledge content.

    Categories: architecture, governance, compliance, technical,
                knowledge, policy, contract.

    All methods are deterministic and compute-only.
    """

    def classify(self, content: ExtractedContent) -> Classification:
        """
        Classify ExtractedContent into one or more categories.

        Scoring combines keyword matching (weighted regex signals) and
        file-path heuristics.  Each category score is clamped to [0, 1].

        Args:
            content: An ExtractedContent record from ContentExtractor.

        Returns:
            Classification with primary_category, all_scores, and
            SHA-256 hashes for input and evidence.
        """
        combined_text = f"{content.title} {content.body}"
        set(Path(content.source_path).parts + tuple(content.source_path.replace("\\", "/").lower().split("/")))
        path_lower = content.source_path.replace("\\", "/").lower()

        raw_scores: dict[str, float] = {cat: 0.0 for cat in CATEGORIES}
        matched_signals: dict[str, list[str]] = {cat: [] for cat in CATEGORIES}

        # Keyword signals
        for cat, signals in _KEYWORD_SIGNALS.items():
            for pattern, label, weight in signals:
                if re.search(pattern, combined_text, re.IGNORECASE):
                    raw_scores[cat] = _clamp(raw_scores[cat] + weight)
                    matched_signals[cat].append(label)

        # Path signals
        for path_seg, cat, weight in _PATH_SIGNALS:
            if path_seg in path_lower:
                raw_scores[cat] = _clamp(raw_scores[cat] + weight)
                matched_signals[cat].append(f"path:{path_seg}")

        # Content-type boosts
        for boost_cat, boost_weight in _TYPE_BOOSTS.get(content.content_type, {}).items():
            raw_scores[boost_cat] = _clamp(raw_scores[boost_cat] + boost_weight)
            matched_signals[boost_cat].append(f"type:{content.content_type}")

        # Floor: if nothing matched, assign a baseline to "knowledge"
        if all(v == 0.0 for v in raw_scores.values()):
            raw_scores["knowledge"] = 0.1
            matched_signals["knowledge"].append("fallback:default")

        # Build CategoryScore list, sorted by score descending
        all_scores = tuple(
            sorted(
                (
                    CategoryScore(
                        category=cat,
                        score=round(raw_scores[cat], 4),
                        matched_signals=tuple(sorted(set(matched_signals[cat]))),
                    )
                    for cat in CATEGORIES
                ),
                key=lambda cs: cs.score,
                reverse=True,
            )
        )

        primary_category = all_scores[0].category

        # Hashes
        input_hash = _sha256_text(content.source_path + content.body)
        evidence_payload: dict[str, Any] = {
            "primary_category": primary_category,
            "scores": {cs.category: cs.score for cs in all_scores},
            "input_hash": input_hash,
        }
        evidence_hash = _sha256_dict(evidence_payload)

        return Classification(
            primary_category=primary_category,
            all_scores=all_scores,
            input_hash=input_hash,
            evidence_hash=evidence_hash,
        )
