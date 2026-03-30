#!/usr/bin/env python3
"""SSID Attack Surface Mapper.

Maps the exposed attack surface of the SSID system by:
  1. Discovering HTTP/RPC endpoint definitions across all roots.
  2. Cataloguing external runtime dependencies (third-party packages,
     external API calls, and database drivers).
  3. Detecting open or configurable network ports.
  4. Categorising each surface entry by risk level.

The mapper operates entirely offline by analysing source files — it does
not make network connections.

Usage:
    python 12_tooling/security/attack_surface_mapper.py --root .
    python 12_tooling/security/attack_surface_mapper.py --root . --output report.json
    python 12_tooling/security/attack_surface_mapper.py --root 03_core --report-only

SoT v4.1.0 | ROOT-24-LOCK
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Risk classification helpers
# ---------------------------------------------------------------------------

#: Risk levels from highest to lowest.
RISK_LEVELS = ("critical", "high", "medium", "low", "info")


def _risk_label(level: int) -> str:
    """Map integer 0-4 to risk label."""
    return RISK_LEVELS[max(0, min(level, len(RISK_LEVELS) - 1))]


# ---------------------------------------------------------------------------
# Endpoint discovery patterns
# ---------------------------------------------------------------------------

#: Patterns that indicate an HTTP / RPC route definition.
#: Each tuple: (framework_hint, compiled_pattern, capture_group_for_path)
_ENDPOINT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # FastAPI / Starlette / Flask decorators
    ("http",  re.compile(r'@(?:app|router)\.(get|post|put|patch|delete|head|options)\s*\(\s*["\']([^"\']+)["\']', re.IGNORECASE)),
    # Django URL patterns
    ("http",  re.compile(r'path\s*\(\s*["\']([^"\']+)["\']', re.IGNORECASE)),
    ("http",  re.compile(r're_path\s*\(\s*["\']([^"\']+)["\']', re.IGNORECASE)),
    # Express.js (JavaScript/TypeScript)
    ("http",  re.compile(r'(?:app|router)\.(get|post|put|patch|delete)\s*\(\s*["\']([^"\']+)["\']', re.IGNORECASE)),
    # gRPC service definitions
    ("grpc",  re.compile(r'\brpc\s+(\w+)\s*\(', re.IGNORECASE)),
    # WebSocket upgrades
    ("ws",    re.compile(r'WebSocket\s*\(|@websocket\s*\(|ws://', re.IGNORECASE)),
    # GraphQL schema type definitions
    ("graphql", re.compile(r'\btype\s+(?:Query|Mutation|Subscription)\s*\{', re.IGNORECASE)),
]

#: Patterns that reveal explicit port numbers.
_PORT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("explicit_bind", re.compile(r'(?:listen|bind|port)\s*[=:({]\s*(\d{2,5})', re.IGNORECASE)),
    ("env_port",      re.compile(r'(?:PORT|LISTEN_PORT|HTTP_PORT|GRPC_PORT)\s*[=:]\s*(\d{2,5})')),
    ("uvicorn_port",  re.compile(r'--port\s+(\d{2,5})')),
    ("docker_expose", re.compile(r'^EXPOSE\s+(\d{2,5})', re.MULTILINE)),
]

#: Known high-risk external dependency patterns.
_HIGH_RISK_DEP_PREFIXES = frozenset({
    "boto3", "botocore", "paramiko", "fabric", "cryptography",
    "pycrypto", "Crypto", "httpx", "aiohttp", "requests", "urllib3",
    "ldap3", "pyotp", "authlib", "jwt", "itsdangerous",
    "sqlalchemy", "tortoise-orm", "motor", "pymongo", "psycopg",
    "redis", "celery", "kombu", "pika",  # message queues
    "kubernetes", "docker", "ansible",
})

#: Patterns for external API call detection.
_EXTERNAL_CALL_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r'https?://[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}(?:/[^\s"\']*)?'),
    re.compile(r'(?:requests|httpx|aiohttp)\s*\.\s*(?:get|post|put|patch|delete|request)\s*\('),
    re.compile(r'fetch\s*\(\s*["\']https?://'),
    re.compile(r'axios\s*\.\s*(?:get|post|put|patch|delete)\s*\('),
]


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class EndpointEntry:
    """A discovered HTTP, RPC, WS, or GraphQL endpoint."""

    file_path: str
    line_number: int
    method: str          # HTTP method, "rpc", "ws", "graphql", or "unknown"
    path: str            # Route path or method name
    framework: str       # "http" | "grpc" | "ws" | "graphql"
    risk_level: str      # "critical" | "high" | "medium" | "low" | "info"
    notes: str = ""


@dataclass
class PortEntry:
    """A discovered network port reference."""

    file_path: str
    line_number: int
    port: int
    binding_type: str    # e.g. "explicit_bind", "env_port", "docker_expose"
    risk_level: str
    notes: str = ""


@dataclass
class DependencyEntry:
    """An external dependency with attack surface relevance."""

    name: str
    version: str
    ecosystem: str       # "pypi" | "npm" | "unknown"
    risk_level: str
    notes: str = ""


@dataclass
class ExternalCallEntry:
    """A detected outbound HTTP / API call."""

    file_path: str
    line_number: int
    target: str          # URL or pattern excerpt
    risk_level: str
    notes: str = ""


@dataclass
class AttackSurfaceReport:
    """Full attack surface report."""

    generated_at: str
    root_path: str
    endpoints: list[EndpointEntry] = field(default_factory=list)
    ports: list[PortEntry] = field(default_factory=list)
    dependencies: list[DependencyEntry] = field(default_factory=list)
    external_calls: list[ExternalCallEntry] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    # Summary counters (populated by generate_report())
    total_endpoints: int = 0
    total_ports: int = 0
    total_dependencies: int = 0
    total_external_calls: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Risk classification logic
# ---------------------------------------------------------------------------

def _endpoint_risk(method: str, path: str) -> str:
    """Assign a risk level to an endpoint based on method and path."""
    m = method.lower()
    p = path.lower()

    # Authentication and admin paths are always high risk
    if any(kw in p for kw in ("admin", "root", "superuser", "/auth/", "/token", "/login", "/logout")):
        return "critical"
    if any(kw in p for kw in ("secret", "key", "password", "credential", "jwt", "oauth")):
        return "critical"
    if m in ("delete", "patch") or any(kw in p for kw in ("delete", "update", "write", "exec", "run")):
        return "high"
    if m in ("post", "put"):
        return "high"
    if any(kw in p for kw in ("internal", "debug", "health", "metrics", "status")):
        return "medium"
    return "low"


def _port_risk(port: int) -> str:
    """Classify a port number by risk."""
    if port in (22, 23, 3389, 5900):   # SSH, Telnet, RDP, VNC
        return "critical"
    if port in (25, 110, 143, 587, 993, 995):  # Mail
        return "high"
    if port in (80, 8080, 3000, 4000, 5000, 5173, 8000, 8888):  # HTTP
        return "medium"
    if port in (443, 8443):             # HTTPS
        return "low"
    if port in (5432, 3306, 27017, 6379, 9200, 5601):  # DB / Cache / Search
        return "high"
    if 1 <= port <= 1023:               # Well-known privileged ports
        return "high"
    return "medium"


def _dep_risk(name: str) -> str:
    """Classify a dependency by its known attack surface relevance."""
    lower = name.lower()
    if any(lower.startswith(p.lower()) for p in ("cryptography", "pycrypto", "nacl", "paramiko")):
        return "high"
    if any(lower.startswith(p.lower()) for p in _HIGH_RISK_DEP_PREFIXES):
        return "medium"
    return "low"


# ---------------------------------------------------------------------------
# Core mapper
# ---------------------------------------------------------------------------

class AttackSurfaceMapper:
    """Map the attack surface of an SSID repository or individual root.

    Args:
        skip_extensions: File extensions to ignore.
        max_file_size: Files larger than this (bytes) are skipped.
    """

    _SKIP_EXTENSIONS = frozenset({
        ".pyc", ".pyo", ".so", ".dll", ".exe", ".bin",
        ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico",
        ".pdf", ".zip", ".tar", ".gz",
        ".whl", ".egg", ".lock",
    })

    def __init__(
        self,
        skip_extensions: frozenset[str] | None = None,
        max_file_size: int = 2 * 1024 * 1024,
    ) -> None:
        self._skip_ext = skip_extensions or self._SKIP_EXTENSIONS
        self._max_size = max_file_size

        self._endpoints: list[EndpointEntry] = []
        self._ports: list[PortEntry] = []
        self._dependencies: list[DependencyEntry] = []
        self._external_calls: list[ExternalCallEntry] = []
        self._errors: list[str] = []
        self._seen_deps: set[str] = set()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def map_endpoints(self, root_dir: Path) -> list[EndpointEntry]:
        """Scan source files under *root_dir* for endpoint definitions.

        Args:
            root_dir: Directory to scan recursively.

        Returns:
            List of discovered EndpointEntry objects.
        """
        if not root_dir.is_dir():
            self._errors.append(f"map_endpoints: not a directory: {root_dir}")
            return []

        new_entries: list[EndpointEntry] = []

        for path in sorted(root_dir.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() in self._skip_ext:
                continue
            if path.suffix.lower() not in (".py", ".ts", ".js", ".go", ".java", ".rb", ".proto"):
                continue

            try:
                size = path.stat().st_size
                if size > self._max_size:
                    continue
                content = path.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                self._errors.append(f"read error: {path}: {exc}")
                continue

            for lineno, line in enumerate(content.splitlines(), start=1):
                for framework, pattern in _ENDPOINT_PATTERNS:
                    match = pattern.search(line)
                    if not match:
                        continue

                    groups = match.groups()
                    if framework == "http" and len(groups) >= 2:
                        method = groups[0].upper() if groups[0] else "GET"
                        route  = groups[1] if len(groups) > 1 else groups[0]
                    elif framework == "grpc" and groups:
                        method = "rpc"
                        route  = groups[0]
                    elif framework in ("ws", "graphql"):
                        method = framework
                        route  = match.group(0)[:60]
                    else:
                        method = "unknown"
                        route  = groups[0] if groups else match.group(0)[:60]

                    entry = EndpointEntry(
                        file_path=str(path),
                        line_number=lineno,
                        method=method,
                        path=route,
                        framework=framework,
                        risk_level=_endpoint_risk(method, route),
                    )
                    new_entries.append(entry)
                    self._endpoints.append(entry)
                    break  # one match per line

        # Detect external API calls in the same pass
        self._scan_external_calls(root_dir)

        return new_entries

    def map_dependencies(self, root_dir: Path) -> list[DependencyEntry]:
        """Extract external dependency risk entries from lock/requirements files.

        Args:
            root_dir: Directory to scan recursively.

        Returns:
            List of DependencyEntry objects with risk classification.
        """
        if not root_dir.is_dir():
            self._errors.append(f"map_dependencies: not a directory: {root_dir}")
            return []

        new_entries: list[DependencyEntry] = []

        # Python requirements / lock files
        _req_re = re.compile(r"^([A-Za-z0-9_.\-]+)==([^\s;#]+)")
        for fname in ("requirements.txt", "requirements.lock", "pdm.lock"):
            for candidate in root_dir.rglob(fname):
                try:
                    for line in candidate.read_text(encoding="utf-8").splitlines():
                        m = _req_re.match(line.strip())
                        if m:
                            name, ver = m.group(1), m.group(2)
                            key = f"pypi:{name.lower()}"
                            if key not in self._seen_deps:
                                self._seen_deps.add(key)
                                entry = DependencyEntry(
                                    name=name,
                                    version=ver,
                                    ecosystem="pypi",
                                    risk_level=_dep_risk(name),
                                )
                                new_entries.append(entry)
                                self._dependencies.append(entry)
                except OSError as exc:
                    self._errors.append(f"dep read error: {candidate}: {exc}")

        # npm package.json
        for pkg_json in root_dir.rglob("package.json"):
            if "node_modules" in pkg_json.parts:
                continue
            try:
                data = json.loads(pkg_json.read_text(encoding="utf-8"))
                for section in ("dependencies", "devDependencies"):
                    for name, ver in data.get(section, {}).items():
                        key = f"npm:{name.lower()}"
                        if key not in self._seen_deps:
                            self._seen_deps.add(key)
                            entry = DependencyEntry(
                                name=name,
                                version=str(ver),
                                ecosystem="npm",
                                risk_level=_dep_risk(name),
                            )
                            new_entries.append(entry)
                            self._dependencies.append(entry)
            except (OSError, json.JSONDecodeError) as exc:
                self._errors.append(f"package.json error: {pkg_json}: {exc}")

        # Scan for explicit port references while we're here
        self._scan_ports(root_dir)

        return new_entries

    def generate_report(self) -> AttackSurfaceReport:
        """Build and return the complete AttackSurfaceReport.

        Returns:
            AttackSurfaceReport populated from all map_* calls so far.
        """
        all_items: list[Any] = (
            self._endpoints + self._ports + self._dependencies + self._external_calls
        )
        critical = sum(1 for i in all_items if getattr(i, "risk_level", "") == "critical")
        high     = sum(1 for i in all_items if getattr(i, "risk_level", "") == "high")
        medium   = sum(1 for i in all_items if getattr(i, "risk_level", "") == "medium")

        return AttackSurfaceReport(
            generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            root_path="(multiple)" if not self._endpoints else self._endpoints[0].file_path,
            endpoints=list(self._endpoints),
            ports=list(self._ports),
            dependencies=list(self._dependencies),
            external_calls=list(self._external_calls),
            errors=list(self._errors),
            total_endpoints=len(self._endpoints),
            total_ports=len(self._ports),
            total_dependencies=len(self._dependencies),
            total_external_calls=len(self._external_calls),
            critical_count=critical,
            high_count=high,
            medium_count=medium,
        )

    def reset(self) -> None:
        """Clear all accumulated state."""
        self._endpoints.clear()
        self._ports.clear()
        self._dependencies.clear()
        self._external_calls.clear()
        self._errors.clear()
        self._seen_deps.clear()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _scan_ports(self, root_dir: Path) -> None:
        """Scan source files for port number references."""
        seen_ports: set[tuple[str, int]] = set()

        for path in sorted(root_dir.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() in self._skip_ext:
                continue
            try:
                size = path.stat().st_size
                if size > self._max_size:
                    continue
                content = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            for lineno, line in enumerate(content.splitlines(), start=1):
                for binding_type, pattern in _PORT_PATTERNS:
                    match = pattern.search(line)
                    if not match:
                        continue
                    try:
                        port = int(match.group(1))
                    except (IndexError, ValueError):
                        continue
                    if port < 1 or port > 65535:
                        continue
                    key = (str(path), port)
                    if key in seen_ports:
                        continue
                    seen_ports.add(key)
                    self._ports.append(PortEntry(
                        file_path=str(path),
                        line_number=lineno,
                        port=port,
                        binding_type=binding_type,
                        risk_level=_port_risk(port),
                    ))
                    break

    def _scan_external_calls(self, root_dir: Path) -> None:
        """Scan source files for outbound HTTP / API calls."""
        for path in sorted(root_dir.rglob("*.py")):
            if not path.is_file():
                continue
            try:
                size = path.stat().st_size
                if size > self._max_size:
                    continue
                content = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            for lineno, line in enumerate(content.splitlines(), start=1):
                for pattern in _EXTERNAL_CALL_PATTERNS:
                    match = pattern.search(line)
                    if not match:
                        continue
                    target = match.group(0)[:80]
                    # Skip internal / localhost URLs
                    if any(h in target for h in ("localhost", "127.0.0.1", "0.0.0.0")):
                        break
                    self._external_calls.append(ExternalCallEntry(
                        file_path=str(path),
                        line_number=lineno,
                        target=target,
                        risk_level="medium",
                    ))
                    break


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(description="SSID Attack Surface Mapper")
    parser.add_argument("--root", type=Path, required=True,
                        help="Root directory to scan (SSID repo root or individual root)")
    parser.add_argument("--output", "-o", type=Path, default=None,
                        help="Write JSON report to this path")
    parser.add_argument("--report-only", action="store_true",
                        help="Print summary only, not full report")
    parser.add_argument("--fail-on-critical", action="store_true",
                        help="Exit non-zero if critical items are found")
    args = parser.parse_args(argv)

    mapper = AttackSurfaceMapper()
    mapper.map_endpoints(args.root)
    mapper.map_dependencies(args.root)
    report = mapper.generate_report()

    report_dict = report.to_dict()

    if args.report_only:
        summary = {
            "generated_at": report.generated_at,
            "total_endpoints": report.total_endpoints,
            "total_ports": report.total_ports,
            "total_dependencies": report.total_dependencies,
            "total_external_calls": report.total_external_calls,
            "critical_count": report.critical_count,
            "high_count": report.high_count,
            "medium_count": report.medium_count,
        }
        print(json.dumps(summary, indent=2))
    elif args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report_dict, indent=2) + "\n", encoding="utf-8")
        print(f"Attack surface report written to {args.output}")
    else:
        print(json.dumps(report_dict, indent=2))

    print(
        f"\nSummary: endpoints={report.total_endpoints}, "
        f"ports={report.total_ports}, "
        f"deps={report.total_dependencies}, "
        f"external_calls={report.total_external_calls} "
        f"[critical={report.critical_count}, high={report.high_count}]",
        file=sys.stderr,
    )

    if args.fail_on_critical and report.critical_count > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
