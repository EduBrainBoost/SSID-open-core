"""ssidctl worker: registry — registry sync and validation.

Usage:
    python -m ssidctl.commands.registry validate --registry <path>
    python -m ssidctl.commands.registry sync --source <path> --target <path>
    python -m ssidctl.commands.registry status
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def _validate(args: argparse.Namespace) -> int:
    """Validate a registry file for structural integrity."""
    registry_path = Path(args.registry)

    if not registry_path.exists():
        error = {
            "command": "registry.validate",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "path": str(registry_path),
            "exists": False,
            "status": "failed",
        }
        print(json.dumps(error, indent=2), file=sys.stderr)
        return 1

    content = registry_path.read_bytes()
    sha256 = hashlib.sha256(content).hexdigest()

    issues = []
    try:
        if registry_path.suffix in (".json",):
            data = json.loads(content)
        elif registry_path.suffix in (".yaml", ".yml"):
            try:
                import yaml
                data = yaml.safe_load(content)
            except ImportError:
                issues.append("PyYAML not installed, cannot validate YAML")
                data = None
        else:
            issues.append(f"Unknown registry format: {registry_path.suffix}")
            data = None

        if data is not None:
            if isinstance(data, dict):
                if "schema_version" not in data:
                    issues.append("Missing schema_version field")
            else:
                issues.append("Registry root must be a mapping/dict")
    except (json.JSONDecodeError, Exception) as exc:
        issues.append(f"Parse error: {exc}")

    output = {
        "command": "registry.validate",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "path": str(registry_path),
        "sha256": sha256,
        "issues": issues,
        "issue_count": len(issues),
        "status": "valid" if not issues else "invalid",
    }
    print(json.dumps(output, indent=2))
    return 1 if issues else 0


def _sync(args: argparse.Namespace) -> int:
    """Sync registry from source to target."""
    source = Path(args.source)
    target = Path(args.target)

    if not source.exists():
        error = {
            "command": "registry.sync",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": str(source),
            "error": "Source does not exist",
            "status": "failed",
        }
        print(json.dumps(error, indent=2), file=sys.stderr)
        return 1

    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    target_hash = hashlib.sha256(target.read_bytes()).hexdigest() if target.exists() else None

    output = {
        "command": "registry.sync",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": str(source),
        "target": str(target),
        "source_sha256": source_hash,
        "target_sha256_before": target_hash,
        "needs_sync": source_hash != target_hash,
        "status": "synced" if source_hash == target_hash else "sync_required",
    }
    print(json.dumps(output, indent=2))
    return 0


def _status(args: argparse.Namespace) -> int:
    """Report registry worker status."""
    output = {
        "command": "registry.status",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "supported_formats": ["json", "yaml"],
        "hash_algorithm": "sha256",
        "canonical_path": "24_meta_orchestration/registry/",
        "mode": "NON_INTERACTIVE",
    }
    print(json.dumps(output, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ssidctl-registry",
        description="SSIDCTL Registry Worker — sync and validation",
    )
    sub = parser.add_subparsers(dest="action", required=True)

    validate_p = sub.add_parser("validate", help="Validate registry file")
    validate_p.add_argument("--registry", required=True, help="Path to registry file")

    sync_p = sub.add_parser("sync", help="Sync registry source to target")
    sync_p.add_argument("--source", required=True, help="Source registry path")
    sync_p.add_argument("--target", required=True, help="Target registry path")

    sub.add_parser("status", help="Registry worker status")

    args = parser.parse_args(argv)

    dispatch_map = {
        "validate": _validate,
        "sync": _sync,
        "status": _status,
    }

    try:
        return dispatch_map[args.action](args)
    except Exception as exc:
        error = {
            "command": f"registry.{args.action}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": str(exc),
            "status": "failed",
        }
        print(json.dumps(error, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
