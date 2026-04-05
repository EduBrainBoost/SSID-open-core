"""content_extractor.py — Extract structured content from SSID knowledge sources.

Compute-only: scans file system paths, parses YAML/JSON/Markdown/policy files,
and returns structured ExtractedContent records with SHA-256 content hashes.

No PII is stored; output is deterministic given the same file contents.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Supported file extensions
# ---------------------------------------------------------------------------

_YAML_EXTENSIONS = {".yaml", ".yml"}
_JSON_EXTENSIONS = {".json"}
_MARKDOWN_EXTENSIONS = {".md", ".markdown"}
_POLICY_EXTENSIONS = {".policy", ".rego"}
_ALL_SUPPORTED = _YAML_EXTENSIONS | _JSON_EXTENSIONS | _MARKDOWN_EXTENSIONS | _POLICY_EXTENSIONS


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceFile:
    """A discovered file ready for extraction."""

    path: str
    extension: str
    size_bytes: int
    content_type: str  # "yaml" | "json" | "markdown" | "policy"


@dataclass(frozen=True)
class ExtractedContent:
    """Structured content extracted from a single source file."""

    title: str
    body: str
    metadata: dict[str, Any]
    content_type: str  # "yaml" | "json" | "markdown" | "policy"
    source_path: str
    hash: str  # SHA-256 of normalised body


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _detect_content_type(ext: str) -> str:
    if ext in _YAML_EXTENSIONS:
        return "yaml"
    if ext in _JSON_EXTENSIONS:
        return "json"
    if ext in _MARKDOWN_EXTENSIONS:
        return "markdown"
    if ext in _POLICY_EXTENSIONS:
        return "policy"
    return "unknown"


def _extract_markdown_title(text: str) -> str:
    """Return first H1 heading, or first non-empty line, or empty string."""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
        if stripped:
            return stripped[:120]
    return ""


def _extract_yaml_title(data: Any, source_path: str) -> str:
    if isinstance(data, dict):
        for key in ("title", "name", "id", "label"):
            if key in data and isinstance(data[key], str):
                return data[key]
    return Path(source_path).stem


def _parse_yaml_safe(text: str) -> Any:
    """Parse YAML without requiring PyYAML; fall back to raw text on failure."""
    try:
        import yaml  # type: ignore[import]

        return yaml.safe_load(text)
    except Exception:
        pass
    # Minimal fallback: return raw text as a string value
    return text


def _flatten_to_text(obj: Any, depth: int = 0) -> str:
    """Recursively flatten nested dicts/lists to a readable text representation."""
    if depth > 8:
        return str(obj)
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        parts = []
        for k, v in obj.items():
            parts.append(f"{k}: {_flatten_to_text(v, depth + 1)}")
        return "\n".join(parts)
    if isinstance(obj, list):
        return "\n".join(_flatten_to_text(item, depth + 1) for item in obj)
    return str(obj)


# ---------------------------------------------------------------------------
# ContentExtractor
# ---------------------------------------------------------------------------


class ContentExtractor:
    """
    Discovers and parses SSID knowledge source files.

    Usage::

        extractor = ContentExtractor()
        sources = extractor.scan_sources(["/path/to/docs", "/path/to/policies"])
        for src in sources:
            content = extractor.extract_content(src)
    """

    def scan_sources(self, paths: list[str]) -> list[SourceFile]:
        """
        Recursively discover all supported files under the given paths.

        Args:
            paths: List of directory or file paths to scan.

        Returns:
            Sorted list of SourceFile records (by path, for determinism).
        """
        found: list[SourceFile] = []
        for raw_path in paths:
            p = Path(raw_path)
            if not p.exists():
                logger.debug("scan_sources: path does not exist: %s", raw_path)
                continue
            if p.is_file():
                sf = self._make_source_file(p)
                if sf is not None:
                    found.append(sf)
            elif p.is_dir():
                for child in sorted(p.rglob("*")):
                    if child.is_file():
                        sf = self._make_source_file(child)
                        if sf is not None:
                            found.append(sf)
        # Deduplicate and sort for determinism
        seen: set[str] = set()
        result: list[SourceFile] = []
        for sf in found:
            if sf.path not in seen:
                seen.add(sf.path)
                result.append(sf)
        return sorted(result, key=lambda s: s.path)

    def _make_source_file(self, path: Path) -> SourceFile | None:
        ext = path.suffix.lower()
        if ext not in _ALL_SUPPORTED:
            return None
        content_type = _detect_content_type(ext)
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        return SourceFile(
            path=str(path),
            extension=ext,
            size_bytes=size,
            content_type=content_type,
        )

    def extract_content(self, source: SourceFile) -> ExtractedContent:
        """
        Parse a SourceFile into structured ExtractedContent.

        Args:
            source: A SourceFile record from scan_sources().

        Returns:
            ExtractedContent with title, body, metadata, content_type,
            source_path, and SHA-256 hash of the body.
        """
        try:
            raw_text = Path(source.path).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            logger.warning("extract_content: cannot read %s — %s", source.path, exc)
            raw_text = ""

        if source.content_type == "markdown":
            return self._extract_markdown(raw_text, source)
        if source.content_type == "yaml":
            return self._extract_yaml(raw_text, source)
        if source.content_type == "json":
            return self._extract_json(raw_text, source)
        if source.content_type == "policy":
            return self._extract_policy(raw_text, source)
        # Fallback
        return self._make_result("", raw_text, {}, source)

    # ------------------------------------------------------------------
    # Format-specific extractors
    # ------------------------------------------------------------------

    def _extract_markdown(self, text: str, source: SourceFile) -> ExtractedContent:
        title = _extract_markdown_title(text)
        # Strip YAML front-matter if present
        metadata: dict[str, Any] = {}
        body = text
        fm_match = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", text, re.DOTALL)
        if fm_match:
            fm_text = fm_match.group(1)
            body = text[fm_match.end() :]
            try:
                import yaml  # type: ignore[import]

                fm_data = yaml.safe_load(fm_text)
                if isinstance(fm_data, dict):
                    metadata = {k: str(v) for k, v in fm_data.items()}
                    if "title" in metadata:
                        title = metadata["title"]
            except Exception:
                pass
        return self._make_result(title, body.strip(), metadata, source)

    def _extract_yaml(self, text: str, source: SourceFile) -> ExtractedContent:
        data = _parse_yaml_safe(text)
        metadata: dict[str, Any] = {}
        if isinstance(data, dict):
            metadata = {k: str(v) for k, v in data.items() if isinstance(v, (str, int, float, bool))}
        title = _extract_yaml_title(data, source.path)
        body = _flatten_to_text(data)
        return self._make_result(title, body, metadata, source)

    def _extract_json(self, text: str, source: SourceFile) -> ExtractedContent:
        metadata: dict[str, Any] = {}
        body = text
        title = Path(source.path).stem
        try:
            data = json.loads(text)
            body = _flatten_to_text(data)
            if isinstance(data, dict):
                for key in ("title", "name", "id", "label"):
                    if key in data and isinstance(data[key], str):
                        title = data[key]
                        break
                metadata = {k: str(v) for k, v in data.items() if isinstance(v, (str, int, float, bool))}
        except json.JSONDecodeError as exc:
            logger.debug("extract_json: parse error in %s — %s", source.path, exc)
        return self._make_result(title, body, metadata, source)

    def _extract_policy(self, text: str, source: SourceFile) -> ExtractedContent:
        title = Path(source.path).stem
        # Try to extract a package name or rule identifier from Rego
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("package "):
                title = stripped[8:].strip()
                break
            if stripped.startswith("# title:"):
                title = stripped[8:].strip()
                break
        return self._make_result(title, text, {"policy_file": Path(source.path).name}, source)

    @staticmethod
    def _make_result(
        title: str,
        body: str,
        metadata: dict[str, Any],
        source: SourceFile,
    ) -> ExtractedContent:
        content_hash = _sha256_text(body)
        return ExtractedContent(
            title=title or Path(source.path).stem,
            body=body,
            metadata=metadata,
            content_type=source.content_type,
            source_path=source.path,
            hash=content_hash,
        )
