#!/usr/bin/env python3
"""SSID Supply-Chain SBOM Export.

Generates a deterministic Software Bill of Materials (SBOM) in JSON format.

Data sources (priority order):
1. requirements.lock (if present) — stable, deterministic
2. poetry.lock / pdm.lock (if present)
3. Fallback: python -m pip freeze — runtime snapshot

Usage:
    python 12_tooling/supply_chain/sbom_export.py --output sbom.json
    python 12_tooling/supply_chain/sbom_export.py --output sbom.json --lockfile requirements.lock
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "1.0"
GENERATOR = "ssid-sbom-export"

# Secret patterns that MUST NOT appear in SBOM output.
DENY_PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),                    # AWS Access Key
    re.compile(r"ghp_[a-zA-Z0-9]{36}"),                 # GitHub Personal Token
    re.compile(r"-----BEGIN (RSA |EC )?PRIVATE KEY-----"),  # PEM Private Key
    re.compile(r"sk-[a-zA-Z0-9]{48}"),                   # OpenAI API Key
    re.compile(r"xox[bprs]-[a-zA-Z0-9\-]+"),            # Slack Token
    re.compile(r"GOCSPX-[a-zA-Z0-9\-_]+"),              # Google OAuth Secret
    re.compile(r"glpat-[a-zA-Z0-9\-_]{20,}"),           # GitLab Personal Token
]


def _sha256_of_file(path: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_of_bytes(data: bytes) -> str:
    """Compute SHA-256 hex digest of bytes."""
    return hashlib.sha256(data).hexdigest()


def _parse_lockfile(path: Path) -> list[dict]:
    """Parse a requirements-style lockfile (one package==version per line)."""
    packages = []
    text = path.read_text(encoding="utf-8")
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        # Handle == and ~= and >= etc. — we only extract name==version
        match = re.match(r"^([A-Za-z0-9_.-]+)==([^\s;#]+)", line)
        if match:
            packages.append({
                "name": match.group(1).lower(),
                "version": match.group(2),
                "source": path.name,
            })
    return sorted(packages, key=lambda p: p["name"])


def _pip_freeze() -> list[dict]:
    """Get packages from pip freeze as fallback."""
    result = subprocess.run(
        [sys.executable, "-m", "pip", "freeze", "--local"],
        capture_output=True,
        text=True,
        check=False,
    )
    packages = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^([A-Za-z0-9_.-]+)==([^\s;#]+)", line)
        if match:
            packages.append({
                "name": match.group(1).lower(),
                "version": match.group(2),
                "source": "pip_freeze",
            })
    return sorted(packages, key=lambda p: p["name"])


def _find_lockfile(search_dir: Path | None = None) -> tuple[Path | None, str]:
    """Find the best lockfile in priority order.

    Returns (path, source_name) or (None, "pip_freeze").
    """
    candidates = [
        "requirements.lock",
        "requirements.txt",
        "poetry.lock",
        "pdm.lock",
    ]
    if search_dir is None:
        search_dir = Path.cwd()
    for name in candidates:
        p = search_dir / name
        if p.exists():
            return p, name
    return None, "pip_freeze"


def _check_secrets(sbom_json: str) -> list[str]:
    """Check SBOM JSON string for secret patterns. Returns list of violations."""
    violations = []
    for pattern in DENY_PATTERNS:
        matches = pattern.findall(sbom_json)
        if matches:
            violations.append(f"Secret pattern matched: {pattern.pattern} ({len(matches)} match(es))")
    return violations


def generate_sbom(
    lockfile: Path | None = None,
    search_dir: Path | None = None,
) -> dict:
    """Generate SBOM dictionary.

    Args:
        lockfile: Explicit lockfile path. If None, auto-detect.
        search_dir: Directory to search for lockfiles. Defaults to cwd.

    Returns:
        SBOM dictionary with schema_version, packages, etc.
    """
    if lockfile and lockfile.exists():
        source = lockfile.name
        input_sha = _sha256_of_file(lockfile)
        packages = _parse_lockfile(lockfile)
    else:
        found, source = _find_lockfile(search_dir)
        if found:
            input_sha = _sha256_of_file(found)
            packages = _parse_lockfile(found)
        else:
            freeze_output = subprocess.run(
                [sys.executable, "-m", "pip", "freeze", "--local"],
                capture_output=True,
                text=True,
                check=False,
            ).stdout
            input_sha = _sha256_of_bytes(freeze_output.encode("utf-8"))
            packages = _pip_freeze()

    return {
        "schema_version": SCHEMA_VERSION,
        "generator": GENERATOR,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": source,
        "input_sha256": input_sha,
        "environment": {
            "python_version": platform.python_version(),
            "platform": sys.platform,
        },
        "packages": packages,
        "package_count": len(packages),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SSID Supply-Chain SBOM Export")
    parser.add_argument(
        "--output", "-o",
        type=Path,
        required=True,
        help="Output path for sbom.json",
    )
    parser.add_argument(
        "--lockfile",
        type=Path,
        default=None,
        help="Explicit lockfile path (default: auto-detect)",
    )
    parser.add_argument(
        "--search-dir",
        type=Path,
        default=None,
        help="Directory to search for lockfiles (default: cwd)",
    )
    args = parser.parse_args(argv)

    sbom = generate_sbom(lockfile=args.lockfile, search_dir=args.search_dir)
    sbom_json = json.dumps(sbom, indent=2, sort_keys=False)

    # Secret pattern guard
    violations = _check_secrets(sbom_json)
    if violations:
        for v in violations:
            print(f"DENY: {v}", file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(sbom_json + "\n", encoding="utf-8")
    print(f"SBOM written to {args.output} ({sbom['package_count']} packages)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
