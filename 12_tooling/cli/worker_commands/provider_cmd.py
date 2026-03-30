"""ssidctl worker: provider — provider health and failover.

Usage:
    python -m ssidctl.commands.provider health --provider <name>
    python -m ssidctl.commands.provider failover --from <provider> --to <provider>
    python -m ssidctl.commands.provider status
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone


KNOWN_PROVIDERS = [
    "sumsub",
    "shufti_pro",
    "blockpass",
    "solidproof",
    "idenfy",
]

PROVIDER_TIERS = {
    "sumsub": "api",
    "shufti_pro": "api",
    "blockpass": "api",
    "solidproof": "cli",
    "idenfy": "api",
}


def _health(args: argparse.Namespace) -> int:
    """Check health of a KYC provider."""
    provider = args.provider

    if provider not in KNOWN_PROVIDERS and provider != "all":
        error = {
            "command": "provider.health",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "provider": provider,
            "error": f"Unknown provider. Known: {KNOWN_PROVIDERS}",
            "status": "failed",
        }
        print(json.dumps(error, indent=2), file=sys.stderr)
        return 1

    targets = KNOWN_PROVIDERS if provider == "all" else [provider]
    results = {}
    for p in targets:
        results[p] = {
            "tier": PROVIDER_TIERS.get(p, "unknown"),
            "reachable": None,
            "last_check": datetime.now(timezone.utc).isoformat(),
            "note": "Health check stub — no live API call",
        }

    output = {
        "command": "provider.health",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "providers_checked": len(targets),
        "results": results,
        "status": "checked",
    }
    print(json.dumps(output, indent=2))
    return 0


def _failover(args: argparse.Namespace) -> int:
    """Trigger failover from one provider to another."""
    from_p = args.source
    to_p = args.target

    for p in [from_p, to_p]:
        if p not in KNOWN_PROVIDERS:
            error = {
                "command": "provider.failover",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": f"Unknown provider: {p}",
                "status": "failed",
            }
            print(json.dumps(error, indent=2), file=sys.stderr)
            return 1

    output = {
        "command": "provider.failover",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "from_provider": from_p,
        "to_provider": to_p,
        "failover_status": "initiated",
        "note": "Failover stub — requires live provider config",
    }
    print(json.dumps(output, indent=2))
    return 0


def _status(args: argparse.Namespace) -> int:
    """Report provider worker status."""
    output = {
        "command": "provider.status",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "known_providers": KNOWN_PROVIDERS,
        "provider_count": len(KNOWN_PROVIDERS),
        "tier_model": "two-tier (api + cli)",
        "failover_enabled": True,
        "mode": "NON_INTERACTIVE",
    }
    print(json.dumps(output, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ssidctl-provider",
        description="SSIDCTL Provider Worker — health and failover",
    )
    sub = parser.add_subparsers(dest="action", required=True)

    health_p = sub.add_parser("health", help="Check provider health")
    health_p.add_argument("--provider", required=True, help="Provider name or 'all'")

    failover_p = sub.add_parser("failover", help="Trigger provider failover")
    failover_p.add_argument("--from", dest="source", required=True, help="Source provider")
    failover_p.add_argument("--to", dest="target", required=True, help="Target provider")

    sub.add_parser("status", help="Provider worker status")

    args = parser.parse_args(argv)

    dispatch_map = {
        "health": _health,
        "failover": _failover,
        "status": _status,
    }

    try:
        return dispatch_map[args.action](args)
    except Exception as exc:
        error = {
            "command": f"provider.{args.action}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": str(exc),
            "status": "failed",
        }
        print(json.dumps(error, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
