"""Runtime smoke-check library — stdlib only, no external dependencies."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

DEFAULT_TIMEOUT_SEC = 3
DEFAULT_ALLOW_STATUS = list(range(200, 400))
EVIDENCE_SUBDIR = "23_compliance/evidence/ci_runs/runtime_smoke_results"


def check_http(
    name: str,
    url: str,
    *,
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
    allow_status: list[int] | None = None,
) -> dict[str, Any]:
    """Check HTTP reachability. Returns a result dict."""
    allowed = allow_status if allow_status is not None else DEFAULT_ALLOW_STATUS
    t0 = time.monotonic()
    try:
        req = Request(url, method="GET")
        resp = urlopen(req, timeout=timeout_sec)  # noqa: S310
        code = resp.status
        elapsed = int((time.monotonic() - t0) * 1000)
        ok = code in allowed
        return {
            "name": name,
            "kind": "http",
            "url": url,
            "status": "PASS" if ok else "FAIL",
            "http_status": code,
            "error": None if ok else f"HTTP {code} not in allow_status",
            "elapsed_ms": elapsed,
        }
    except URLError as exc:
        elapsed = int((time.monotonic() - t0) * 1000)
        return {
            "name": name,
            "kind": "http",
            "url": url,
            "status": "FAIL",
            "http_status": None,
            "error": str(exc.reason),
            "elapsed_ms": elapsed,
        }
    except Exception as exc:  # noqa: BLE001
        elapsed = int((time.monotonic() - t0) * 1000)
        return {
            "name": name,
            "kind": "http",
            "url": url,
            "status": "FAIL",
            "http_status": None,
            "error": str(exc),
            "elapsed_ms": elapsed,
        }


def check_http_error_status(
    name: str,
    url: str,
    *,
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
    allow_status: list[int] | None = None,
) -> dict[str, Any]:
    """Check HTTP target that may return error status codes (4xx/5xx).

    urllib raises HTTPError for non-2xx responses, so we catch that
    and check the status code against allow_status.
    """
    allowed = allow_status if allow_status is not None else DEFAULT_ALLOW_STATUS
    t0 = time.monotonic()
    try:
        req = Request(url, method="GET")
        resp = urlopen(req, timeout=timeout_sec)  # noqa: S310
        code = resp.status
        elapsed = int((time.monotonic() - t0) * 1000)
        ok = code in allowed
        return {
            "name": name,
            "kind": "http",
            "url": url,
            "status": "PASS" if ok else "FAIL",
            "http_status": code,
            "error": None if ok else f"HTTP {code} not in allow_status",
            "elapsed_ms": elapsed,
        }
    except URLError as exc:
        elapsed = int((time.monotonic() - t0) * 1000)
        # HTTPError is a subclass of URLError and has a .code attribute
        code = getattr(exc, "code", None)
        if code is not None and code in allowed:
            return {
                "name": name,
                "kind": "http",
                "url": url,
                "status": "PASS",
                "http_status": code,
                "error": None,
                "elapsed_ms": elapsed,
            }
        return {
            "name": name,
            "kind": "http",
            "url": url,
            "status": "FAIL",
            "http_status": code,
            "error": str(exc.reason) if code is None else f"HTTP {code} not in allow_status",
            "elapsed_ms": elapsed,
        }
    except Exception as exc:  # noqa: BLE001
        elapsed = int((time.monotonic() - t0) * 1000)
        return {
            "name": name,
            "kind": "http",
            "url": url,
            "status": "FAIL",
            "http_status": None,
            "error": str(exc),
            "elapsed_ms": elapsed,
        }


def check_ws_skip(name: str, url: str, *, reason: str = "stdlib-only; ws not supported") -> dict[str, Any]:
    """Return a SKIP result for WebSocket targets."""
    return {
        "name": name,
        "kind": "ws",
        "url": url,
        "status": "SKIP",
        "http_status": None,
        "error": None,
        "elapsed_ms": 0,
        "skip_reason": reason,
    }


def run_target(target: dict[str, Any], *, default_timeout: int = DEFAULT_TIMEOUT_SEC) -> dict[str, Any]:
    """Dispatch a single target check based on kind and mode."""
    kind = target.get("kind", "http")
    mode = target.get("mode", "check")
    name = target["name"]
    url = target["url"]
    timeout = target.get("timeout_sec", default_timeout)
    allow_status = target.get("allow_status")

    if kind == "ws" and mode == "skip":
        return check_ws_skip(name, url)

    if kind == "ws":
        return check_ws_skip(name, url, reason="ws check requires external dependency; skipped")

    # For HTTP targets that may return 4xx/5xx codes we want to allow
    if allow_status and any(s >= 400 for s in allow_status):
        return check_http_error_status(name, url, timeout_sec=timeout, allow_status=allow_status)

    return check_http(name, url, timeout_sec=timeout, allow_status=allow_status)


def run_all(config: dict[str, Any]) -> dict[str, Any]:
    """Run all targets from a config dict and return a payload."""
    default_timeout = config.get("timeout_sec", DEFAULT_TIMEOUT_SEC)
    results = [run_target(t, default_timeout=default_timeout) for t in config["targets"]]
    return build_payload(results)


def build_payload(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the evidence payload from results."""
    from datetime import datetime, timezone

    return {
        "schema_version": "1.0",
        "run_utc": datetime.now(timezone.utc).isoformat(),
        "targets": results,
    }


def payload_sha256(payload: dict[str, Any]) -> str:
    """Compute SHA-256 hex digest of the JSON-serialized payload."""
    raw = json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def write_evidence(payload: dict[str, Any], base_dir: str | Path) -> Path:
    """Write evidence JSON to the canonical path. Returns the file path."""
    json_str = json.dumps(payload, indent=2, ensure_ascii=False)
    sha = hashlib.sha256(json_str.encode("utf-8")).hexdigest()
    out_dir = Path(base_dir) / EVIDENCE_SUBDIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"RUNTIME_SMOKE_{sha}.json"
    out_file.write_text(json_str, encoding="utf-8")
    return out_file


def evaluate_results(payload: dict[str, Any]) -> bool:
    """Return True if all targets are PASS or SKIP (no FAIL)."""
    return all(t["status"] in ("PASS", "SKIP") for t in payload["targets"])
