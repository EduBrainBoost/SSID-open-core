#!/usr/bin/env python3
"""
SSID Runtime Verification Script

Checks all workspace (G) ports from the canonical port-policy and generates
a runtime_verification_report.json in the same directory.

Ports checked (Workspace / G-Environment):
  3100  - SSID-EMS Portal Frontend
  8100  - SSID-EMS Portal Backend
  3310  - SSID-Orchestrator API
  5273  - SSID-Orchestrator Web UI
  4331  - SSID-docs
  4332  - CCT Dashboard

Dependencies: stdlib + requests (requests is optional; falls back to socket).

Usage:
    python verify_runtime.py                  # check all ports
    python verify_runtime.py --canonical      # check canonical (C) ports instead
    python verify_runtime.py --output FILE    # custom output path
"""

import argparse
import datetime
import json
import os
import socket
import sys

try:
    import requests as _requests
except ImportError:
    _requests = None

# ---------------------------------------------------------------------------
# Port matrix
# ---------------------------------------------------------------------------

WORKSPACE_PORTS = {
    3100: "SSID-EMS Portal Frontend",
    8100: "SSID-EMS Portal Backend",
    3310: "SSID-Orchestrator API",
    5273: "SSID-Orchestrator Web UI",
    4331: "SSID-docs",
    4332: "CCT Dashboard",
}

CANONICAL_PORTS = {
    3000: "SSID-EMS Portal Frontend",
    8000: "SSID-EMS Portal Backend",
    3210: "SSID-Orchestrator API",
    5173: "SSID-Orchestrator Web UI",
    4321: "SSID-docs",
    4322: "CCT Dashboard",
}

# ---------------------------------------------------------------------------
# Probes
# ---------------------------------------------------------------------------


def check_tcp(host: str, port: int, timeout: float = 2.0) -> bool:
    """Return True if a TCP connection succeeds."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def check_http(host: str, port: int, path: str = "/", timeout: float = 3.0) -> dict:
    """Try an HTTP GET and return status info. Falls back to TCP if requests is unavailable."""
    result = {
        "tcp_open": check_tcp(host, port, timeout),
        "http_status": None,
        "http_ok": False,
    }
    if not result["tcp_open"]:
        return result

    if _requests is not None:
        try:
            resp = _requests.get(
                f"http://{host}:{port}{path}",
                timeout=timeout,
                allow_redirects=True,
            )
            result["http_status"] = resp.status_code
            result["http_ok"] = resp.ok
        except _requests.RequestException:
            pass
    return result


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


def run_verification(ports: dict, host: str = "localhost") -> dict:
    """Check every port and return the verification report dict."""
    results = []
    up_count = 0
    down_count = 0

    for port, service in sorted(ports.items()):
        probe = check_http(host, port)
        status = "UP" if probe["tcp_open"] else "DOWN"
        if status == "UP":
            up_count += 1
        else:
            down_count += 1

        entry = {
            "port": port,
            "service": service,
            "status": status,
            "tcp_open": probe["tcp_open"],
            "http_status": probe["http_status"],
            "http_ok": probe["http_ok"],
        }
        results.append(entry)

    report = {
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "host": host,
        "environment": "workspace" if 3100 in ports else "canonical",
        "total_services": len(ports),
        "up": up_count,
        "down": down_count,
        "all_healthy": down_count == 0,
        "services": results,
    }
    return report


def print_summary(report: dict) -> None:
    """Print a human-readable summary to stdout."""
    env_label = report["environment"].upper()
    print(f"\n=== SSID Runtime Verification ({env_label}) ===")
    print(f"Timestamp : {report['timestamp']}")
    print(f"Host      : {report['host']}")
    print(f"Services  : {report['up']}/{report['total_services']} UP\n")

    for svc in report["services"]:
        icon = "[UP]  " if svc["status"] == "UP" else "[DOWN]"
        http_info = ""
        if svc["http_status"] is not None:
            http_info = f"  HTTP {svc['http_status']}"
        print(f"  {icon} :{svc['port']}  {svc['service']}{http_info}")

    print()
    if report["all_healthy"]:
        print("Result: ALL SERVICES HEALTHY")
    else:
        print(f"Result: {report['down']} service(s) DOWN")
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify SSID runtime services by checking port availability.",
    )
    parser.add_argument(
        "--canonical",
        action="store_true",
        help="Check canonical (C) ports instead of workspace (G) ports.",
    )
    parser.add_argument(
        "--host",
        default="localhost",
        help="Host to check (default: localhost).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output path for the JSON report (default: runtime_verification_report.json next to this script).",
    )
    args = parser.parse_args()

    ports = CANONICAL_PORTS if args.canonical else WORKSPACE_PORTS
    report = run_verification(ports, host=args.host)
    print_summary(report)

    output_path = args.output
    if output_path is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_path = os.path.join(script_dir, "runtime_verification_report.json")

    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
    print(f"Report written to: {output_path}")

    return 0 if report["all_healthy"] else 1


if __name__ == "__main__":
    sys.exit(main())
