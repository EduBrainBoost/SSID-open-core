"""
URL/File ingest adapter for SWS Analyze Spine.

Handles:
- Local file ingestion (path validation, hash computation)
- URL-based ingestion (download to staging, hash computation)
- Rights-to-ingest handoff (validates rights token before proceeding)
- Source manifest generation
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


@dataclass
class RightsToken:
    """Represents a rights-to-ingest authorization token."""

    token_id: str
    issuer: str
    granted_at: str
    permissions: list[str] = field(default_factory=lambda: ["ingest", "analyze"])
    expires_at: Optional[str] = None

    def is_valid(self) -> bool:
        if self.expires_at is None:
            return True
        exp = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
        return datetime.now(timezone.utc) < exp

    def has_permission(self, perm: str) -> bool:
        return perm in self.permissions


@dataclass
class IngestResult:
    """Result of an ingest operation."""

    source_id: str
    local_path: Path
    source_hash: str
    file_size_bytes: int
    ingested_at: str
    origin: str  # "file" or "url"
    original_reference: str  # original path or URL


class IngestError(Exception):
    """Raised when ingestion fails."""


class RightsError(Exception):
    """Raised when rights validation fails."""


def _compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _generate_source_id(original_ref: str) -> str:
    ref_hash = hashlib.sha256(original_ref.encode("utf-8")).hexdigest()[:12]
    return f"src_{ref_hash}"


def validate_rights(rights_token: Optional[RightsToken]) -> None:
    """Validate rights-to-ingest token. Raises RightsError if invalid."""
    if rights_token is None:
        raise RightsError("No rights token provided. Ingest requires authorization.")
    if not rights_token.is_valid():
        raise RightsError(f"Rights token {rights_token.token_id} has expired.")
    if not rights_token.has_permission("ingest"):
        raise RightsError(
            f"Rights token {rights_token.token_id} lacks 'ingest' permission."
        )


def ingest_file(
    file_path: str | Path,
    staging_dir: str | Path,
    rights_token: Optional[RightsToken] = None,
) -> IngestResult:
    """
    Ingest a local file into the staging directory.

    Args:
        file_path: Path to the source media file.
        staging_dir: Directory to stage the ingested file.
        rights_token: Authorization token for ingest.

    Returns:
        IngestResult with source metadata.

    Raises:
        IngestError: If the file doesn't exist or can't be read.
        RightsError: If rights validation fails.
    """
    validate_rights(rights_token)

    source = Path(file_path)
    if not source.exists():
        raise IngestError(f"Source file does not exist: {source}")
    if not source.is_file():
        raise IngestError(f"Source path is not a file: {source}")

    staging = Path(staging_dir)
    staging.mkdir(parents=True, exist_ok=True)

    source_id = _generate_source_id(str(source.resolve()))
    dest = staging / source.name

    shutil.copy2(source, dest)

    source_hash = _compute_sha256(dest)
    file_size = dest.stat().st_size

    return IngestResult(
        source_id=source_id,
        local_path=dest,
        source_hash=source_hash,
        file_size_bytes=file_size,
        ingested_at=datetime.now(timezone.utc).isoformat(),
        origin="file",
        original_reference=str(source.resolve()),
    )


def ingest_url(
    url: str,
    staging_dir: str | Path,
    rights_token: Optional[RightsToken] = None,
    timeout: int = 120,
) -> IngestResult:
    """
    Ingest media from a URL into the staging directory.

    Args:
        url: URL of the media asset.
        staging_dir: Directory to stage the downloaded file.
        rights_token: Authorization token for ingest.
        timeout: Download timeout in seconds.

    Returns:
        IngestResult with source metadata.

    Raises:
        IngestError: If download fails.
        RightsError: If rights validation fails.
    """
    validate_rights(rights_token)

    staging = Path(staging_dir)
    staging.mkdir(parents=True, exist_ok=True)

    source_id = _generate_source_id(url)

    # Derive filename from URL
    url_path = url.split("?")[0].split("#")[0]
    filename = os.path.basename(url_path) or f"{source_id}.media"
    dest = staging / filename

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SWS-Ingest/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            with open(dest, "wb") as f:
                shutil.copyfileobj(resp, f)
    except Exception as exc:
        raise IngestError(f"Failed to download from {url}: {exc}") from exc

    source_hash = _compute_sha256(dest)
    file_size = dest.stat().st_size

    return IngestResult(
        source_id=source_id,
        local_path=dest,
        source_hash=source_hash,
        file_size_bytes=file_size,
        ingested_at=datetime.now(timezone.utc).isoformat(),
        origin="url",
        original_reference=url,
    )


def build_source_manifest(
    ingest_result: IngestResult,
    width: int,
    height: int,
    frame_rate: float,
    duration_seconds: float,
    codec_video: str,
    codec_audio: str,
    sample_rate: int,
    channels: int,
) -> dict:
    """
    Build a source_manifest.json-conformant dict from ingest result + probe data.

    The probe data (width, height, codec, etc.) comes from the media_normalize step.
    """
    return {
        "source_id": ingest_result.source_id,
        "filename": ingest_result.local_path.name,
        "duration_seconds": duration_seconds,
        "width": width,
        "height": height,
        "frame_rate": frame_rate,
        "codec_video": codec_video,
        "codec_audio": codec_audio,
        "sample_rate": sample_rate,
        "channels": channels,
        "file_size_bytes": ingest_result.file_size_bytes,
        "created_timestamp": ingest_result.ingested_at,
        "source_hash": ingest_result.source_hash,
    }
