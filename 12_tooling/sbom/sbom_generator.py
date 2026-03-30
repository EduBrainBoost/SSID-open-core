#!/usr/bin/env python3
"""SBOM (Software Bill of Materials) generator for SSID.

DEPRECATED: This module contains hardcoded components and is no longer used by CI.
Use 12_tooling/supply_chain/sbom_export.py instead, which reads from lockfiles
and produces deterministic, lockfile-based SBOMs with secret-pattern guards.

This file is retained for reference only (SAFE-FIX: additive, not deleted).

Generates a CycloneDX-compliant Software Bill of Materials.
"""
import warnings
warnings.warn(
    "sbom_generator.py is deprecated. Use 12_tooling/supply_chain/sbom_export.py instead.",
    DeprecationWarning,
    stacklevel=2,
)
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
import uuid


def extract_dependencies() -> dict[str, Any]:
    """Extract Python dependencies."""
    packages = {}

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "show", "-f", "pytest"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        pass

    return packages


def generate_sbom() -> dict[str, Any]:
    """Generate a CycloneDX SBOM."""
    components = [
        {
            "type": "library",
            "name": "pytest",
            "version": "9.0.2",
            "purl": "pkg:pypi/pytest@9.0.2",
            "licenses": [{"license": {"name": "MIT"}}],
            "scope": "required",
        },
        {
            "type": "library",
            "name": "pyyaml",
            "version": "6.0.1",
            "purl": "pkg:pypi/pyyaml@6.0.1",
            "licenses": [{"license": {"name": "MIT"}}],
            "scope": "required",
        },
        {
            "type": "library",
            "name": "jsonschema",
            "version": "4.21.1",
            "purl": "pkg:pypi/jsonschema@4.21.1",
            "licenses": [{"license": {"name": "MIT"}}],
            "scope": "required",
        },
        {
            "type": "library",
            "name": "pydantic",
            "version": "2.5.0",
            "purl": "pkg:pypi/pydantic@2.5.0",
            "licenses": [{"license": {"name": "MIT"}}],
            "scope": "required",
        },
        {
            "type": "library",
            "name": "jinja2",
            "version": "3.1.2",
            "purl": "pkg:pypi/jinja2@3.1.2",
            "licenses": [{"license": {"name": "BSD-3-Clause"}}],
            "scope": "required",
        },
    ]

    sbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.4",
        "serialNumber": f"urn:uuid:{uuid.uuid4()}",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now().isoformat() + "Z",
            "tools": [
                {
                    "vendor": "SSID",
                    "name": "sbom-generator",
                    "version": "1.0.0",
                }
            ],
            "component": {
                "type": "application",
                "name": "SSID",
                "version": "1.0.0",
                "description": "Smart SSID Identity and Delegation framework",
            },
        },
        "components": components,
    }

    return sbom


def main():
    """Generate and save SBOM."""
    print("Generating SBOM (CycloneDX format)...")

    sbom = generate_sbom()

    output_file = Path("sbom/sbom.json")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(sbom, indent=2))

    print(f"SBOM generated: {output_file}")
    print(f"  Components: {len(sbom['components'])}")
    print(f"  Format: CycloneDX {sbom['specVersion']}")

    manifest = {
        "sbom_version": sbom["specVersion"],
        "components_count": len(sbom["components"]),
        "generated_at": sbom["metadata"]["timestamp"],
        "components_summary": [
            {"name": c["name"], "version": c["version"]}
            for c in sbom["components"]
        ],
    }

    manifest_file = Path("sbom/manifest.json")
    manifest_file.write_text(json.dumps(manifest, indent=2))
    print(f"Manifest generated: {manifest_file}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
