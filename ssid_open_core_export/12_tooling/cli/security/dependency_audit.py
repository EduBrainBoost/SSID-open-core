#!/usr/bin/env python3
"""Dependency audit for SSID repository.

Checks for known vulnerabilities in Python dependencies.
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

KNOWN_VULNERABILITIES = {}


def extract_requirements() -> dict[str, str]:
    """Extract installed packages and versions."""
    packages = {}

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "freeze"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        for line in result.stdout.strip().split("\n"):
            if "==" in line:
                name, version = line.split("==")
                packages[name.lower()] = version
    except Exception:
        pass

    return packages


def check_vulnerabilities(packages: dict[str, str]) -> list[dict[str, Any]]:
    """Check installed packages against known vulnerabilities."""
    findings = []

    for pkg_name, vuln_specs in KNOWN_VULNERABILITIES.items():
        if pkg_name not in packages:
            continue

        installed_version = packages[pkg_name]
        for pattern, cve, description in vuln_specs:
            if _version_matches_pattern(installed_version, pattern):
                findings.append(
                    {
                        "package": pkg_name,
                        "installed_version": installed_version,
                        "cve": cve,
                        "description": description,
                        "severity": "CRITICAL" if "Critical" in description else "HIGH",
                    }
                )

    return findings


def _version_matches_pattern(version: str, pattern: str) -> bool:
    """Check if version matches a vulnerability pattern."""
    try:
        if pattern.startswith("<"):
            required = pattern[1:]
            return _compare_versions(version, required) < 0
        elif pattern.startswith("<="):
            required = pattern[2:]
            return _compare_versions(version, required) <= 0
        elif pattern.startswith("=="):
            required = pattern[2:]
            return version == required
    except Exception:
        pass

    return False


def _compare_versions(v1: str, v2: str) -> int:
    """Compare two version strings."""
    try:
        v1_parts = [int(x) for x in v1.split(".")[:3]]
        v2_parts = [int(x) for x in v2.split(".")[:3]]

        while len(v1_parts) < 3:
            v1_parts.append(0)
        while len(v2_parts) < 3:
            v2_parts.append(0)

        if v1_parts < v2_parts:
            return -1
        elif v1_parts > v2_parts:
            return 1
        return 0
    except Exception:
        return 0


def main():
    """Run dependency audit."""
    print("Extracting dependencies...")
    packages = extract_requirements()

    print(f"Found {len(packages)} installed packages")

    print("Checking for known vulnerabilities...")
    vulnerabilities = check_vulnerabilities(packages)

    results = {
        "total_packages": len(packages),
        "vulnerabilities_found": len(vulnerabilities),
        "vulnerabilities": vulnerabilities,
        "packages_sampled": list(sorted(packages.keys()))[:20],
    }

    output_file = Path("security/dependency-audit.json")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(results, indent=2))

    print("Dependency audit complete:")
    print(f"  Total packages: {results['total_packages']}")
    print(f"  Vulnerabilities found: {results['vulnerabilities_found']}")

    if vulnerabilities:
        print("\nVulnerabilities:")
        for vuln in vulnerabilities:
            print(f"  {vuln['cve']}: {vuln['package']} {vuln['installed_version']}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
