"""ssidctl worker: dispatch — task dispatch to workers.

Usage:
    python -m ssidctl.commands.dispatch send --task <task_id> --worker <worker>
    python -m ssidctl.commands.dispatch queue --list
    python -m ssidctl.commands.dispatch status --task <task_id>
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone


VALID_WORKERS = [
    "supervisor", "dispatch", "build", "test", "browser",
    "policy", "audit", "registry", "provider", "release", "repair",
]


def _send(args: argparse.Namespace) -> int:
    """Send a task to a specific worker."""
    if args.worker not in VALID_WORKERS:
        error = {
            "command": "dispatch.send",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": f"Unknown worker: {args.worker}. Valid: {VALID_WORKERS}",
            "status": "rejected",
        }
        print(json.dumps(error, indent=2), file=sys.stderr)
        return 1

    output = {
        "command": "dispatch.send",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "task_id": args.task,
        "target_worker": args.worker,
        "priority": args.priority,
        "dispatch_status": "sent",
        "estimated_start": datetime.now(timezone.utc).isoformat(),
    }
    print(json.dumps(output, indent=2))
    return 0


def _queue(args: argparse.Namespace) -> int:
    """List dispatch queue."""
    output = {
        "command": "dispatch.queue",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "queue_items": [],
        "total_pending": 0,
        "total_in_progress": 0,
    }
    print(json.dumps(output, indent=2))
    return 0


def _status(args: argparse.Namespace) -> int:
    """Check status of a dispatched task."""
    output = {
        "command": "dispatch.status",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "task_id": args.task,
        "status": "unknown",
        "worker": None,
        "started_at": None,
        "completed_at": None,
    }
    print(json.dumps(output, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ssidctl-dispatch",
        description="SSIDCTL Dispatch Worker — task routing to workers",
    )
    sub = parser.add_subparsers(dest="action", required=True)

    send_p = sub.add_parser("send", help="Send task to worker")
    send_p.add_argument("--task", required=True, help="Task ID")
    send_p.add_argument("--worker", required=True, help="Target worker name")
    send_p.add_argument("--priority", default="normal", choices=["low", "normal", "high", "critical"])

    sub.add_parser("queue", help="List dispatch queue")

    status_p = sub.add_parser("status", help="Check task status")
    status_p.add_argument("--task", required=True, help="Task ID to check")

    args = parser.parse_args(argv)

    dispatch_map = {
        "send": _send,
        "queue": _queue,
        "status": _status,
    }

    try:
        return dispatch_map[args.action](args)
    except Exception as exc:
        error = {
            "command": f"dispatch.{args.action}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": str(exc),
            "status": "failed",
        }
        print(json.dumps(error, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
