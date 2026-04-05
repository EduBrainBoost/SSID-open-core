"""content_transformer.py — Normalise, enrich, and package extracted content.

Compute-only: transforms ExtractedContent through two stages (normalise → enrich)
and produces KnowledgeArtifact records ready for indexing.

No PII is handled; all outputs are deterministic given identical inputs.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

from .content_extractor import ExtractedContent

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NormalizedContent:
    """Whitespace-normalised, formatting-stripped content."""

    title: str
    body: str  # Plain text, no markdown/YAML syntax noise
    metadata: dict[str, Any]
    content_type: str
    source_path: str
    hash: str  # SHA-256 of normalised body


@dataclass(frozen=True)
class EnrichedContent:
    """NormalizedContent plus inferred tags, categories, and cross-references."""

    title: str
    body: str
    metadata: dict[str, Any]
    content_type: str
    source_path: str
    hash: str
    tags: tuple[str, ...]
    categories: tuple[str, ...]
    cross_references: tuple[str, ...]  # referenced source paths or IDs


@dataclass(frozen=True)
class KnowledgeArtifact:
    """Final packaged artifact ready for indexing and search."""

    artifact_id: str  # SHA-256 of (source_path + body_hash)
    title: str
    body: str
    summary: str  # First 400 chars of body
    metadata: dict[str, Any]
    content_type: str
    source_path: str
    hash: str
    tags: tuple[str, ...]
    categories: tuple[str, ...]
    cross_references: tuple[str, ...]
    artifact_hash: str  # SHA-256 of full artifact (audit trail)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_dict(data: dict[str, Any]) -> str:
    serialised = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(serialised).hexdigest()


_MARKDOWN_HEADING = re.compile(r"^#{1,6}\s+", re.MULTILINE)
_MARKDOWN_BOLD_ITALIC = re.compile(r"[*_]{1,3}(.+?)[*_]{1,3}")
_MARKDOWN_CODE_BLOCK = re.compile(r"```.*?```", re.DOTALL)
_MARKDOWN_INLINE_CODE = re.compile(r"`[^`]+`")
_MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_MARKDOWN_IMAGE = re.compile(r"!\[([^\]]*)\]\([^)]+\)")
_MARKDOWN_HTML = re.compile(r"<[^>]+>")
_WHITESPACE_RUNS = re.compile(r"\s{2,}")
_YAML_KEY_VALUE = re.compile(r"^\s*[\w\-]+:\s*", re.MULTILINE)


def _strip_markdown(text: str) -> str:
    """Remove markdown formatting tokens, leaving plain text."""
    text = _MARKDOWN_CODE_BLOCK.sub(" ", text)
    text = _MARKDOWN_IMAGE.sub(r"\1", text)
    text = _MARKDOWN_LINK.sub(r"\1", text)
    text = _MARKDOWN_INLINE_CODE.sub(" ", text)
    text = _MARKDOWN_HEADING.sub("", text)
    text = _MARKDOWN_BOLD_ITALIC.sub(r"\1", text)
    text = _MARKDOWN_HTML.sub(" ", text)
    return text


def _normalise_whitespace(text: str) -> str:
    lines = [line.strip() for line in text.splitlines()]
    # Collapse consecutive blank lines to one
    result: list[str] = []
    prev_blank = False
    for line in lines:
        if line == "":
            if not prev_blank:
                result.append("")
            prev_blank = True
        else:
            result.append(line)
            prev_blank = False
    return "\n".join(result).strip()


_SSID_INTERNAL_REF = re.compile(
    r"\b(?:SSID|EMS|module|policy|contract|decision|governance)\b[_\-]?\w*",
    re.IGNORECASE,
)

_TAG_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bgovernance\b", re.I), "governance"),
    (re.compile(r"\bpolicy\b", re.I), "policy"),
    (re.compile(r"\bcontract\b", re.I), "contract"),
    (re.compile(r"\bcompliance\b", re.I), "compliance"),
    (re.compile(r"\barchitecture\b", re.I), "architecture"),
    (re.compile(r"\btechnical\b|\bimplementation\b|\bAPI\b", re.I), "technical"),
    (re.compile(r"\bknowledge\b|\bcodex\b|\bdocumentation\b", re.I), "knowledge"),
    (re.compile(r"\bdecision\b|\bADR\b", re.I), "decision"),
    (re.compile(r"\bsecurity\b|\baudit\b|\bevidence\b", re.I), "security"),
    (re.compile(r"\bagent\b|\borchestrator\b", re.I), "agent"),
]


def _infer_tags(title: str, body: str, content_type: str, source_path: str) -> list[str]:
    combined = f"{title} {body} {source_path}".lower()
    tags: list[str] = [content_type]
    for pattern, tag in _TAG_PATTERNS:
        if pattern.search(combined):
            tags.append(tag)
    # Path-based tags
    parts = source_path.replace("\\", "/").lower().split("/")
    for part in parts:
        if part in {"policies", "contracts", "decisions", "docs", "shards", "codex", "governance"}:
            tags.append(part.rstrip("s"))  # normalise plural
    return sorted(set(tags))


def _infer_categories(title: str, body: str, source_path: str) -> list[str]:
    """Return ordered list of inferred category labels."""
    combined = f"{title} {body} {source_path}".lower()
    path_parts = source_path.replace("\\", "/").lower().split("/")
    cats: set[str] = set()

    if any(p in path_parts for p in ("policies", "policy")):
        cats.add("policy")
    if any(p in path_parts for p in ("contracts", "contract")):
        cats.add("contract")
    if any(p in path_parts for p in ("decisions", "adr")):
        cats.add("governance")
    if any(p in path_parts for p in ("docs", "documentation", "05_documentation")):
        cats.add("knowledge")
    if any(p in path_parts for p in ("16_codex", "codex")):
        cats.add("knowledge")
    if any(p in path_parts for p in ("03_core", "engines", "src")):
        cats.add("technical")
    if re.search(r"\barchitecture\b|\badr\b|\bdesign\b", combined):
        cats.add("architecture")
    if re.search(r"\bcompliance\b|\baudit\b|\bregulatory\b", combined):
        cats.add("compliance")
    if not cats:
        cats.add("knowledge")  # default
    return sorted(cats)


def _find_cross_references(body: str, source_path: str) -> list[str]:
    """Extract internal SSID cross-references from body text."""
    matches = set(_SSID_INTERNAL_REF.findall(body))
    refs = sorted(m for m in matches if m.lower() not in source_path.lower())
    return refs[:20]  # cap at 20 to keep artifacts compact


# ---------------------------------------------------------------------------
# ContentTransformer
# ---------------------------------------------------------------------------


class ContentTransformer:
    """
    Two-stage transformer: normalise → enrich → package as KnowledgeArtifact.

    All methods are compute-only and deterministic.
    """

    def normalize(self, content: ExtractedContent) -> NormalizedContent:
        """
        Strip formatting and unify structure.

        For markdown: remove heading markers, bold/italic, links.
        For all types: collapse whitespace, strip leading/trailing blank lines.

        Returns:
            NormalizedContent with clean plain-text body and SHA-256 of that body.
        """
        body = content.body
        if content.content_type == "markdown":
            body = _strip_markdown(body)
        body = _normalise_whitespace(body)
        norm_hash = _sha256_text(body)
        return NormalizedContent(
            title=content.title.strip(),
            body=body,
            metadata=content.metadata,
            content_type=content.content_type,
            source_path=content.source_path,
            hash=norm_hash,
        )

    def enrich(self, content: NormalizedContent) -> EnrichedContent:
        """
        Add inferred tags, categories, and cross-references.

        Tags are derived from content keywords and file path.
        Categories use the same classification vocabulary as ContentClassifier.
        Cross-references are extracted SSID-internal identifiers.

        Returns:
            EnrichedContent with tags, categories, cross_references.
        """
        tags = _infer_tags(content.title, content.body, content.content_type, content.source_path)
        categories = _infer_categories(content.title, content.body, content.source_path)
        cross_refs = _find_cross_references(content.body, content.source_path)
        return EnrichedContent(
            title=content.title,
            body=content.body,
            metadata=content.metadata,
            content_type=content.content_type,
            source_path=content.source_path,
            hash=content.hash,
            tags=tuple(tags),
            categories=tuple(categories),
            cross_references=tuple(cross_refs),
        )

    def to_knowledge_artifact(self, content: EnrichedContent) -> KnowledgeArtifact:
        """
        Package enriched content as a KnowledgeArtifact ready for indexing.

        artifact_id: deterministic SHA-256 of (source_path + body_hash).
        artifact_hash: SHA-256 of the full serialised artifact payload.

        Returns:
            KnowledgeArtifact (frozen dataclass).
        """
        artifact_id = _sha256_text(content.source_path + content.hash)
        summary = content.body[:400].strip()

        # Build the audit payload — everything except artifact_hash itself
        audit_payload: dict[str, Any] = {
            "artifact_id": artifact_id,
            "title": content.title,
            "body_hash": content.hash,
            "source_path": content.source_path,
            "content_type": content.content_type,
            "tags": list(content.tags),
            "categories": list(content.categories),
        }
        artifact_hash = _sha256_dict(audit_payload)

        return KnowledgeArtifact(
            artifact_id=artifact_id,
            title=content.title,
            body=content.body,
            summary=summary,
            metadata=dict(content.metadata),
            content_type=content.content_type,
            source_path=content.source_path,
            hash=content.hash,
            tags=content.tags,
            categories=content.categories,
            cross_references=content.cross_references,
            artifact_hash=artifact_hash,
        )
