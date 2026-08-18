"""SSID OpenCore — Public Open-Core Mirror.

Provides sanitized public-facing content from SSID Product Core.
One-way export: SSID -> OpenCore (never reverse).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class ExportManifest:
    """Manifest for exported public content."""
    manifest_id: str
    source_repo: str
    export_path: str
    content_hash: str
    exported_at: str
    status: str = "EXPORTED"  # EXPORTED, VERIFIED, REVOKED


class OpenCoreCore:
    """OpenCore core — public mirror management."""

    # Paths allowed for export
    ALLOWED_EXPORT_PATHS = {
        "schemas",
        "public",
        "docs/public",
        "licenses",
        "README.md",
    }

    # Paths to exclude
    EXCLUDED_PATHS = {
        "src/private",
        "config/secrets",
        ".env",
        "secrets",
        "private",
        "internal",
    }

    def __init__(self, core_root: str = "..") -> None:
        self._core_root = Path(core_root)
        self._exports: Dict[str, ExportManifest] = {}
        self._manifests: List[Dict[str, Any]] = []

    def list_exportable(self) -> List[Dict[str, Any]]:
        """List content eligible for export."""
        exports = []
        for path_str in self.ALLOWED_EXPORT_PATHS:
            path = self._core_root / path_str
            if path.exists():
                exports.append({
                    "path": path_str,
                    "type": "directory" if path.is_dir() else "file",
                    "exists": True,
                })
        return exports

    def export_content(self, source_path: str, dest_path: str) -> Optional[ExportManifest]:
        """Export content from core to OpenCore."""
        # Validate path
        if not self._is_allowed_path(source_path):
            return None

        source = self._core_root / source_path
        if not source.exists():
            return None

        # Read and sanitize
        content = self._read_and_sanitize(source)
        if content is None:
            return None

        # Create export manifest
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        manifest_id = f"{source_path.replace('/', '-')}_{content_hash}"

        manifest = ExportManifest(
            manifest_id=manifest_id,
            source_repo="SSID",
            export_path=dest_path,
            content_hash=content_hash,
            exported_at=datetime.now(timezone.utc).isoformat(),
        )
        self._exports[manifest_id] = manifest
        self._manifests.append({
            "manifest_id": manifest_id,
            "source_path": source_path,
            "dest_path": dest_path,
            "content_hash": content_hash,
            "exported_at": manifest.exported_at,
            "status": "EXPORTED",
        })
        return manifest

    def verify_export(self, manifest_id: str) -> Dict[str, Any]:
        """Verify an export manifest."""
        manifest = self._exports.get(manifest_id)
        if not manifest:
            return {"verified": False, "error": "Manifest not found"}

        return {
            "verified": True,
            "manifest_id": manifest.manifest_id,
            "source_repo": manifest.source_repo,
            "export_path": manifest.export_path,
            "content_hash": manifest.content_hash,
            "exported_at": manifest.exported_at,
            "status": manifest.status,
        }

    def list_exports(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all exports."""
        results = []
        for m in self._manifests:
            if status and m["status"] != status:
                continue
            results.append(m)
        return results

    def revoke_export(self, manifest_id: str) -> bool:
        """Revoke an export."""
        manifest = self._exports.get(manifest_id)
        if not manifest:
            return False
        manifest.status = "REVOKED"
        for m in self._manifests:
            if m["manifest_id"] == manifest_id:
                m["status"] = "REVOKED"
                break
        return True

    def _is_allowed_path(self, path: str) -> bool:
        """Check if path is allowed for export."""
        for excluded in self.EXCLUDED_PATHS:
            if excluded in path:
                return False
        return True

    def _read_and_sanitize(self, path: Path) -> Optional[str]:
        """Read file content and sanitize for public export."""
        if path.is_dir():
            return None  # Only export files
        try:
            content = path.read_text(encoding="utf-8")
            # Basic sanitization
            content = content.replace("PRIVATE", "PUBLIC")
            content = content.replace("SECRET", "公开")
            return content
        except (UnicodeDecodeError, PermissionError):
            return None

    def get_schema(self, schema_name: str) -> Optional[Dict[str, Any]]:
        """Get a public schema definition."""
        schema_path = self._core_root / "schemas" / f"{schema_name}.json"
        if not schema_path.exists():
            return None
        try:
            return json.loads(schema_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, PermissionError):
            return None


__version__ = "1.0.0"
__all__ = ["OpenCoreCore", "ExportManifest"]
