"""EMS Reporter — fire-and-forget HTTP result reporter for AR scripts.

Usage:
    from ssid_autorunner.ems_reporter import post_result
    post_result(ems_url, ar_id, run_id, result, commit_sha)

Uses only stdlib (urllib.request). Never raises. Timeout: 5 seconds.
"""
from __future__ import annotations

import json
import socket
import sys
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.error import URLError


@dataclass
class EMSReporterResult:
    sent: bool
    status_code: int = 0
    error: str | None = None


def post_result(
    ems_url: str,
    ar_id: str,
    run_id: str,
    result: dict,
    commit_sha: str,
    timeout: int = 5,
) -> EMSReporterResult:
    """POST AR result to EMS /api/autorunner/ar-results.

    Fire-and-forget: never raises, returns EMSReporterResult.
    If ems_url is empty/None, returns sent=False without attempting HTTP.
    """
    if not ems_url:
        return EMSReporterResult(sent=False, error="ems_url not set")

    endpoint = ems_url.rstrip("/") + "/api/autorunner/ar-results"
    payload = {
        "ar_id": ar_id,
        "run_id": run_id,
        "status": result.get("status", "UNKNOWN"),
        "commit_sha": commit_sha,
        "ts": datetime.now(timezone.utc).isoformat(),
        "findings": result.get("total_findings", result.get("findings", 0)),
        "summary": result.get("summary", ""),
        **{k: v for k, v in result.items()
           if k not in ("status", "total_findings", "findings", "summary")},
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return EMSReporterResult(sent=True, status_code=resp.status)
    except (URLError, socket.timeout, OSError) as exc:
        print(f"[ems_reporter] WARNING: could not reach EMS at {endpoint}: {exc}", file=sys.stderr)
        return EMSReporterResult(sent=False, error=str(exc))
