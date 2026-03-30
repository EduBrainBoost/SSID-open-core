#!/usr/bin/env python3
"""SSID SBOM Generator — CycloneDX format.

Scans all SSID roots for Python and npm dependencies and generates a
CycloneDX v1.4 Software Bill of Materials (JSON).

Data sources (priority order per root):
  1. requirements.lock / requirements.txt (Python)
  2. poetry.lock / pdm.lock (Python)
  3. package-lock.json / yarn.lock (npm/Node)
  4. Fallback: pip freeze (Python runtime snapshot)

Usage:
    python 12_tooling/security/sbom_generator.py --output sbom_cyclonedx.json
    python 12_tooling/security/sbom_generator.py --root 03_core --output out.json

SoT v4.1.0 | ROOT-24-LOCK
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CYCLONEDX_SCHEMA = "http://cyclonedx.org/schema/bom-1.4.schema.json"
CYCLONEDX_VERSION = "1.4"
GENERATOR = "ssid-sbom-generator"
SOT_VERSION = "4.1.0"

SSID_ROOTS = [
    "01_ai_layer", "02_audit_logging", "03_core", "04_deployment",
    "05_documentation", "06_data_pipeline", "07_governance_legal",
    "08_identity_score", "09_meta_identity", "10_interoperability",
    "11_test_simulation", "12_tooling", "13_ui_layer", "14_zero_time_auth",
    "15_infra", "16_codex", "17_observability", "18_data_layer",
    "19_adapters", "20_foundation", "21_post_quantum_crypto", "22_datasets",
    "23_compliance", "24_meta_orchestration",
]

# Secret patterns — output is scrubbed before writing.
_SECRET_PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"ghp_[a-zA-Z0-9]{36}"),
    re.compile(r"-----BEGIN (RSA |EC )?PRIVATE KEY-----"),
    re.compile(r"sk-[a-zA-Z0-9]{48}"),
    re.compile(r"xox[bprs]-[a-zA-Z0-9\-]+"),
    re.compile(r"GOCSPX-[a-zA-Z0-9\-_]+"),
    re.compile(r"glpat-[a-zA-Z0-9\-_]{20,}"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sha256(data: bytes | str) -> str:
    """Return SHA-256 hex digest of bytes or UTF-8 string."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    """Return SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _check_secrets(text: str) -> list[str]:
    """Return a list of secret-pattern violations found in *text*."""
    violations: list[str] = []
    for pat in _SECRET_PATTERNS:
        hits = pat.findall(text)
        if hits:
            violations.append(f"Secret pattern '{pat.pattern}' matched ({len(hits)} occurrence(s))")
    return violations


def _bom_ref(name: str, version: str) -> str:
    """Deterministic BOM ref for a component."""
    return f"pkg:{name.lower()}@{version}"


# ---------------------------------------------------------------------------
# Python dependency parsers
# ---------------------------------------------------------------------------

def _parse_requirements(path: Path) -> list[dict[str, str]]:
    """Parse requirements.txt / requirements.lock style file."""
    components: list[dict[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "-")):
            continue
        m = re.match(r"^([A-Za-z0-9_.-]+)==([^\s;#]+)", line)
        if m:
            components.append({
                "type": "library",
                "name": m.group(1).lower(),
                "version": m.group(2),
                "purl": f"pkg:pypi/{m.group(1).lower()}@{m.group(2)}",
                "bom-ref": _bom_ref(m.group(1), m.group(2)),
                "source": path.name,
            })
    return components


def _parse_poetry_lock(path: Path) -> list[dict[str, str]]:
    """Parse poetry.lock for package names and versions (TOML-lite parser)."""
    components: list[dict[str, str]] = []
    text = path.read_text(encoding="utf-8")
    blocks = re.split(r"\[\[package\]\]", text)
    for block in blocks[1:]:
        name_m = re.search(r'^name\s*=\s*"([^"]+)"', block, re.MULTILINE)
        ver_m = re.search(r'^version\s*=\s*"([^"]+)"', block, re.MULTILINE)
        if name_m and ver_m:
            name, ver = name_m.group(1).lower(), ver_m.group(1)
            components.append({
                "type": "library",
                "name": name,
                "version": ver,
                "purl": f"pkg:pypi/{name}@{ver}",
                "bom-ref": _bom_ref(name, ver),
                "source": "poetry.lock",
            })
    return components


def _pip_freeze_components() -> list[dict[str, str]]:
    """Collect installed packages via pip freeze as last-resort fallback."""
    result = subprocess.run(
        [sys.executable, "-m", "pip", "freeze", "--local"],
        capture_output=True, text=True, check=False,
    )
    components: list[dict[str, str]] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z0-9_.-]+)==([^\s;#]+)", line)
        if m:
            name, ver = m.group(1).lower(), m.group(2)
            components.append({
                "type": "library",
                "name": name,
                "version": ver,
                "purl": f"pkg:pypi/{name}@{ver}",
                "bom-ref": _bom_ref(name, ver),
                "source": "pip_freeze",
            })
    return components


# ---------------------------------------------------------------------------
# npm dependency parsers
# ---------------------------------------------------------------------------

def _parse_package_lock(path: Path) -> list[dict[str, str]]:
    """Parse package-lock.json v2/v3 for npm components."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    components: list[dict[str, str]] = []
    packages = data.get("packages", {})
    for pkg_path, info in packages.items():
        if not pkg_path or pkg_path == "":
            continue  # skip root
        name = pkg_path.lstrip("node_modules/").split("/node_modules/")[-1]
        ver = info.get("version", "unknown")
        components.append({
            "type": "library",
            "name": name,
            "version": ver,
            "purl": f"pkg:npm/{name}@{ver}",
            "bom-ref": _bom_ref(name, ver),
            "source": "package-lock.json",
        })
    return components


# ---------------------------------------------------------------------------
# Root scanner
# ---------------------------------------------------------------------------

def scan_root(root_dir: Path) -> list[dict[str, str]]:
    """Scan a single SSID root for dependencies.

    Returns a list of CycloneDX component dicts (without duplicates).
    """
    seen: set[str] = set()
    components: list[dict[str, str]] = []

    def _add(items: list[dict[str, str]]) -> None:
        for item in items:
            key = item["bom-ref"]
            if key not in seen:
                seen.add(key)
                components.append(item)

    # Python lockfiles — priority order
    for name in ("requirements.lock", "requirements.txt", "pdm.lock"):
        candidate = root_dir / name
        if candidate.exists():
            _add(_parse_requirements(candidate))
            break
    else:
        poetry = root_dir / "poetry.lock"
        if poetry.exists():
            _add(_parse_poetry_lock(poetry))

    # npm
    pkg_lock = root_dir / "package-lock.json"
    if pkg_lock.exists():
        _add(_parse_package_lock(pkg_lock))

    return components


def scan_all_roots(repo_root: Path) -> list[dict[str, Any]]:
    """Scan all SSID roots and return deduplicated CycloneDX components."""
    seen: set[str] = set()
    all_components: list[dict[str, Any]] = []

    for root_name in SSID_ROOTS:
        root_dir = repo_root / root_name
        if not root_dir.is_dir():
            continue
        for comp in scan_root(root_dir):
            if comp["bom-ref"] not in seen:
                seen.add(comp["bom-ref"])
                all_components.append(comp)

    # Fallback: pip freeze if no components found
    if not all_components:
        for comp in _pip_freeze_components():
            if comp["bom-ref"] not in seen:
                seen.add(comp["bom-ref"])
                all_components.append(comp)

    return sorted(all_components, key=lambda c: (c["name"], c["version"]))


# ---------------------------------------------------------------------------
# CycloneDX SBOM builder
# ---------------------------------------------------------------------------

def generate_cyclonedx_sbom(
    repo_root: Path,
    root_filter: str | None = None,
) -> dict[str, Any]:
    """Generate a CycloneDX v1.4 SBOM dict.

    Args:
        repo_root: Path to the SSID repository root.
        root_filter: If set, only scan this specific root name.

    Returns:
        CycloneDX SBOM as a dict ready for JSON serialisation.
    """
    if root_filter:
        root_dir = repo_root / root_filter
        components = scan_root(root_dir)
    else:
        components = scan_all_roots(repo_root)

    bom_serial = f"urn:uuid:{uuid.uuid4()}"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    return {
        "bomFormat": "CycloneDX",
        "specVersion": CYCLONEDX_VERSION,
        "$schema": CYCLONEDX_SCHEMA,
        "serialNumber": bom_serial,
        "version": 1,
        "metadata": {
            "timestamp": timestamp,
            "tools": [{"vendor": "SSID", "name": GENERATOR, "version": SOT_VERSION}],
            "component": {
                "type": "application",
                "name": "SSID",
                "version": SOT_VERSION,
                "description": "Self-Sovereign Identity Daemon",
            },
        },
        "components": components,
        "ssid_meta": {
            "generator": GENERATOR,
            "sot_version": SOT_VERSION,
            "python_version": platform.python_version(),
            "platform": sys.platform,
            "root_filter": root_filter or "all",
            "component_count": len(components),
        },
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(description="SSID CycloneDX SBOM Generator")
    parser.add_argument("--output", "-o", type=Path, required=True,
                        help="Output path for the CycloneDX SBOM JSON")
    parser.add_argument("--repo-root", type=Path, default=None,
                        help="SSID repo root (default: auto-detect from script location)")
    parser.add_argument("--root", type=str, default=None,
                        help="Only scan this SSID root (e.g. '03_core')")
    args = parser.parse_args(argv)

    repo_root = args.repo_root or Path(__file__).resolve().parents[2]

    sbom = generate_cyclonedx_sbom(repo_root=repo_root, root_filter=args.root)
    sbom_json = json.dumps(sbom, indent=2, sort_keys=False)

    violations = _check_secrets(sbom_json)
    if violations:
        for v in violations:
            print(f"DENY: {v}", file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(sbom_json + "\n", encoding="utf-8")
    count = sbom["ssid_meta"]["component_count"]
    print(f"CycloneDX SBOM written to {args.output} ({count} components)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
