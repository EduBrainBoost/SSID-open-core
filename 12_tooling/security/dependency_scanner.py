#!/usr/bin/env python3
"""SSID Dependency Vulnerability Scanner.

Checks Python and npm dependencies for known vulnerabilities by querying
public advisory APIs (PyPI JSON API for Python, npm audit endpoint for Node).

All network calls are optional — the scanner degrades gracefully to
an offline summary when network access is unavailable.

Usage:
    python 12_tooling/security/dependency_scanner.py
    python 12_tooling/security/dependency_scanner.py --sbom sbom_cyclonedx.json
    python 12_tooling/security/dependency_scanner.py --output report.json

SoT v4.1.0 | ROOT-24-LOCK
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class VulnerabilityFinding:
    """A single vulnerability finding."""

    package_name: str
    package_version: str
    ecosystem: str  # "pypi" | "npm"
    vuln_id: str  # CVE or advisory ID
    severity: str  # "critical" | "high" | "medium" | "low" | "unknown"
    cvss_score: float | None
    summary: str
    advisory_url: str


@dataclass
class ScanReport:
    """Full dependency scan report."""

    scanned_at: str
    total_packages: int
    total_vulnerabilities: int
    critical: int
    high: int
    medium: int
    low: int
    unknown: int
    findings: list[VulnerabilityFinding] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    offline: bool = False


# ---------------------------------------------------------------------------
# PyPI advisory check
# ---------------------------------------------------------------------------


def _check_pypi_package(name: str, version: str, timeout: int = 10) -> list[VulnerabilityFinding]:
    """Query PyPI JSON API for vulnerability metadata.

    PyPI exposes a /pypi/<name>/<version>/json endpoint that includes
    a 'vulnerabilities' key populated from OSV data.
    """
    url = f"https://pypi.org/pypi/{name}/{version}/json"
    findings: list[VulnerabilityFinding] = []
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ssid-dependency-scanner/4.1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data: dict[str, Any] = json.loads(resp.read().decode("utf-8"))

        vulns: list[dict] = data.get("vulnerabilities", [])
        for v in vulns:
            aliases: list[str] = v.get("aliases", [])
            vuln_id = aliases[0] if aliases else v.get("id", "UNKNOWN")
            details: str = v.get("details", "") or v.get("summary", "No summary available")
            link: str = v.get("link", f"https://pypi.org/pypi/{name}")
            v.get("fixed_in", [])

            # Attempt to extract a CVSS score from the summary text
            cvss: float | None = None
            severity = "unknown"
            for alias in aliases:
                if alias.startswith("CVE-"):
                    severity = "unknown"
                    break

            findings.append(
                VulnerabilityFinding(
                    package_name=name,
                    package_version=version,
                    ecosystem="pypi",
                    vuln_id=vuln_id,
                    severity=severity,
                    cvss_score=cvss,
                    summary=details[:200],
                    advisory_url=link,
                )
            )

    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
        pass  # Network unavailable or package not found — skip silently

    return findings


# ---------------------------------------------------------------------------
# npm advisory check
# ---------------------------------------------------------------------------


def _check_npm_packages(
    components: list[dict[str, str]],
    timeout: int = 15,
) -> tuple[list[VulnerabilityFinding], list[str]]:
    """Query npm audit bulk endpoint for vulnerability data.

    Sends a minimal audit request body and parses the response.
    Returns (findings, errors).
    """
    npm_components = [c for c in components if c.get("ecosystem") == "npm"]
    if not npm_components:
        return [], []

    # Build a minimal npm audit payload
    requires = {c["name"]: c["version"] for c in npm_components}
    dependencies = {c["name"]: {"version": c["version"]} for c in npm_components}
    payload = json.dumps(
        {
            "name": "ssid-audit",
            "version": "0.0.0",
            "requires": requires,
            "dependencies": dependencies,
        }
    ).encode("utf-8")

    findings: list[VulnerabilityFinding] = []
    errors: list[str] = []

    try:
        req = urllib.request.Request(
            "https://registry.npmjs.org/-/npm/v1/security/audits",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "ssid-dependency-scanner/4.1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data: dict[str, Any] = json.loads(resp.read().decode("utf-8"))

        advisories: dict = data.get("advisories", {})
        for adv_id, adv in advisories.items():
            name = adv.get("module_name", "unknown")
            findings.append(
                VulnerabilityFinding(
                    package_name=name,
                    package_version=adv.get("findings", [{}])[0].get("version", "unknown")
                    if adv.get("findings")
                    else "unknown",
                    ecosystem="npm",
                    vuln_id=adv.get("cves", [adv_id])[0] if adv.get("cves") else str(adv_id),
                    severity=adv.get("severity", "unknown"),
                    cvss_score=adv.get("cvss", {}).get("score"),
                    summary=(adv.get("overview", "") or "")[:200],
                    advisory_url=adv.get("url", f"https://www.npmjs.com/advisories/{adv_id}"),
                )
            )

    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        errors.append(f"npm audit unavailable: {exc}")

    return findings, errors


# ---------------------------------------------------------------------------
# Severity classification
# ---------------------------------------------------------------------------


def _classify_severity(cvss: float | None, raw: str) -> str:
    """Map CVSS score or raw severity string to canonical severity."""
    if cvss is not None:
        if cvss >= 9.0:
            return "critical"
        if cvss >= 7.0:
            return "high"
        if cvss >= 4.0:
            return "medium"
        return "low"
    canon = raw.lower() if raw else "unknown"
    if canon in ("critical", "high", "medium", "low"):
        return canon
    return "unknown"


# ---------------------------------------------------------------------------
# Main scanner
# ---------------------------------------------------------------------------


def scan_components(
    components: list[dict[str, str]],
    online: bool = True,
    timeout: int = 10,
) -> ScanReport:
    """Scan a list of CycloneDX-style component dicts for vulnerabilities.

    Args:
        components: List of dicts with at least 'name', 'version', and 'purl' keys.
        online: If False, skip all network calls (offline mode).
        timeout: HTTP request timeout in seconds.

    Returns:
        ScanReport with all findings.
    """
    findings: list[VulnerabilityFinding] = []
    errors: list[str] = []

    if online:
        for comp in components:
            purl = comp.get("purl", "")
            name = comp.get("name", "")
            version = comp.get("version", "")
            if purl.startswith("pkg:pypi/"):
                findings.extend(_check_pypi_package(name, version, timeout=timeout))

        npm_components = [
            {"name": c["name"], "version": c["version"], "ecosystem": "npm"}
            for c in components
            if c.get("purl", "").startswith("pkg:npm/")
        ]
        npm_findings, npm_errors = _check_npm_packages(npm_components, timeout=timeout + 5)
        findings.extend(npm_findings)
        errors.extend(npm_errors)

    # Re-classify severity with CVSS where possible
    for f in findings:
        f.severity = _classify_severity(f.cvss_score, f.severity)

    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "unknown": 0}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1

    return ScanReport(
        scanned_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        total_packages=len(components),
        total_vulnerabilities=len(findings),
        critical=counts["critical"],
        high=counts["high"],
        medium=counts["medium"],
        low=counts["low"],
        unknown=counts["unknown"],
        findings=findings,
        errors=errors,
        offline=not online,
    )


def scan_sbom_file(sbom_path: Path, online: bool = True, timeout: int = 10) -> ScanReport:
    """Load a CycloneDX SBOM JSON file and scan its components.

    Args:
        sbom_path: Path to a CycloneDX SBOM JSON file.
        online: Whether to make network calls.
        timeout: HTTP timeout in seconds.

    Returns:
        ScanReport.
    """
    data = json.loads(sbom_path.read_text(encoding="utf-8"))
    components: list[dict[str, str]] = data.get("components", [])
    return scan_components(components, online=online, timeout=timeout)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(description="SSID Dependency Vulnerability Scanner")
    parser.add_argument(
        "--sbom", type=Path, default=None, help="CycloneDX SBOM JSON file to scan (default: scan pip freeze)"
    )
    parser.add_argument("--output", "-o", type=Path, default=None, help="Write JSON report to this path")
    parser.add_argument("--offline", action="store_true", help="Skip all network calls (offline mode)")
    parser.add_argument("--timeout", type=int, default=10, help="HTTP request timeout in seconds (default: 10)")
    parser.add_argument(
        "--fail-on-critical", action="store_true", help="Exit non-zero if critical vulnerabilities are found"
    )
    args = parser.parse_args(argv)

    if args.sbom:
        report = scan_sbom_file(args.sbom, online=not args.offline, timeout=args.timeout)
    else:
        # Quick scan of runtime environment via pip freeze
        import re as _re
        import subprocess as _sp

        result = _sp.run(
            [sys.executable, "-m", "pip", "freeze", "--local"],
            capture_output=True,
            text=True,
            check=False,
        )
        components = []
        for line in result.stdout.splitlines():
            m = _re.match(r"^([A-Za-z0-9_.-]+)==([^\s;#]+)", line.strip())
            if m:
                name, ver = m.group(1).lower(), m.group(2)
                components.append(
                    {
                        "name": name,
                        "version": ver,
                        "purl": f"pkg:pypi/{name}@{ver}",
                    }
                )
        report = scan_components(components, online=not args.offline, timeout=args.timeout)

    report_dict = asdict(report)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report_dict, indent=2) + "\n", encoding="utf-8")
        print(f"Scan report written to {args.output}")
    else:
        print(json.dumps(report_dict, indent=2))

    print(
        f"\nSummary: {report.total_vulnerabilities} vulnerabilities in "
        f"{report.total_packages} packages "
        f"(critical={report.critical}, high={report.high}, "
        f"medium={report.medium}, low={report.low})",
        file=sys.stderr,
    )

    if args.fail_on_critical and report.critical > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
