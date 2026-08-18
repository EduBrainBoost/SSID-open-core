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


__version__ = "1.0.0"

ROOT_24 = [
    "01_ai_layer",
    "02_audit_logging",
    "03_core",
    "04_deployment",
    "05_documentation",
    "06_data_pipeline",
    "07_governance_legal",
    "08_identity_score",
    "09_meta_identity",
    "10_interoperability",
    "11_test_simulation",
    "12_tooling",
    "13_ui_layer",
    "14_zero_time_auth",
    "15_infra",
    "16_codex",
    "17_observability",
    "18_data_layer",
    "19_adapters",
    "20_foundation",
    "21_post_quantum_crypto",
    "22_datasets",
    "23_compliance",
    "24_meta_orchestration",
]

ALLOWED_EXPORT_PATHS = {
    "schemas",
    "public",
    "docs/public",
    "licenses",
    "README.md",
}

EXCLUDED_PATHS = {
    "src/private",
    "config/secrets",
    ".env",
    "secrets",
    "private",
    "internal",
}


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

    ALLOWED_EXPORT_PATHS = {
        "schemas",
        "public",
        "docs/public",
        "licenses",
        "README.md",
    }

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
        if not self._is_allowed_path(source_path):
            return None

        source = self._core_root / source_path
        if not source.exists():
            return None

        content = self._read_and_sanitize(source)
        if content is None:
            return None

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
        """Verify an export by manifest ID."""
        manifest = self._exports.get(manifest_id)
        if manifest is None:
            return {"verified": False, "status": "NOT_FOUND"}
        return {"verified": True, "status": manifest.status}

    def revoke_export(self, manifest_id: str) -> bool:
        """Revoke an export."""
        manifest = self._exports.get(manifest_id)
        if manifest is None:
            return False
        manifest.status = "REVOKED"
        for m in self._manifests:
            if m["manifest_id"] == manifest_id:
                m["status"] = "REVOKED"
        return True

    def list_exports(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all exports, optionally filtered by status."""
        if status is None:
            return list(self._manifests)
        return [m for m in self._manifests if m["status"] == status]

    def _is_allowed_path(self, path: str) -> bool:
        """Check if a path is allowed for export."""
        for excluded in self.EXCLUDED_PATHS:
            if path.startswith(excluded):
                return False
        for allowed in self.ALLOWED_EXPORT_PATHS:
            if path.startswith(allowed):
                return True
        return False

    def _read_and_sanitize(self, path: Path) -> Optional[str]:
        """Read a file and sanitize private content."""
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                content = path.read_bytes().decode("utf-8", errors="replace")
            except Exception:
                return None
        # Sanitize: remove absolute Windows paths
        import re
        sanitized = re.sub(r'C:\\Users\\[^\\]+\\SSID-Workspace\\[^\\]+', '[REDACTED_WORKSPACE]', content)
        sanitized = re.sub(r'C:\\Users\\[^\\]+\\Documents\\Github\\[^\\]+', '[REDACTED_DOCS]', sanitized)
        return sanitized

    def validate_root_24(self) -> Dict[str, Any]:
        """Validate that all 24 roots exist with required files."""
        root_dir = self._core_root
        results = {"valid": True, "roots": {}, "errors": []}
        for root in ROOT_24:
            root_path = root_dir / root
            exists = root_path.exists()
            has_readme = (root_path / "README.md").exists() if exists else False
            has_module = (root_path / "module.yaml").exists() if exists else False
            status = "VALID" if (exists and has_readme and has_module) else ("MISSING" if not exists else "INCOMPLETE")
            results["roots"][root] = {"exists": exists, "has_readme": has_readme, "has_module": has_module, "status": status}
            if status != "VALID":
                results["valid"] = False
                results["errors"].append(f"{root}: {status}")
        return results
