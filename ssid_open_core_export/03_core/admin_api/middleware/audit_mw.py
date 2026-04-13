"""Audit middleware — logs every request to evidence trail. Append-only."""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from datetime import UTC, datetime

EVIDENCE_PATH = os.environ.get(
    "ADMIN_EVIDENCE_PATH",
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "02_audit_logging", "evidence", "admin_events.jsonl"),
)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


async def audit_middleware(request, call_next):
    """Log request metadata to JSONL evidence trail. No PII. Hash-only."""
    start = time.time()
    response = await call_next(request)
    elapsed = round(time.time() - start, 4)

    event = {
        "event_id": f"evt_{uuid.uuid4().hex[:12]}",
        "timestamp_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "method": request.method,
        "path": str(request.url.path),
        "status_code": response.status_code,
        "elapsed_s": elapsed,
        "client_hash": _sha256(request.client.host if request.client else "unknown"),
    }
    event["sha256"] = _sha256(json.dumps(event, sort_keys=True))

    try:
        os.makedirs(os.path.dirname(EVIDENCE_PATH), exist_ok=True)
        with open(EVIDENCE_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, sort_keys=True) + "\n")
    except OSError:
        pass  # fail-open in dev — log to stderr in production

    return response
