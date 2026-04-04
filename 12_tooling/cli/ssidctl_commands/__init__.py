#!/usr/bin/env python3
"""ssidctl governance CLI subcommands registry.

This module registers all 11 ssidctl governance subcommands with a shared
argparse subparser. Each command module exposes a ``build_parser`` function
that accepts an optional ``subparsers`` action for integration.
"""

from __future__ import annotations

import argparse

from . import (
    approval,
    changeset,
    federation,
    federation_ops,
    governance,
    incident,
    promote,
    remediation,
    resilience,
    sot_diff,
    verification,
)

# Canonical command registry: CLI name -> module
COMMAND_REGISTRY: dict[str, object] = {
    "sot-diff": sot_diff,
    "promote": promote,
    "governance": governance,
    "remediation": remediation,
    "approval": approval,
    "changeset": changeset,
    "verification": verification,
    "federation": federation,
    "federation-ops": federation_ops,
    "incident": incident,
    "resilience": resilience,
}


def register_all(subparsers: argparse._SubParsersAction) -> None:
    """Register all 11 governance subcommands with the given subparsers action."""
    for _name, module in COMMAND_REGISTRY.items():
        module.build_parser(subparsers)  # type: ignore[attr-defined]


def get_command_names() -> list[str]:
    """Return sorted list of all registered command names."""
    return sorted(COMMAND_REGISTRY.keys())


__all__ = [
    "COMMAND_REGISTRY",
    "register_all",
    "get_command_names",
    "approval",
    "changeset",
    "federation",
    "federation_ops",
    "governance",
    "incident",
    "promote",
    "remediation",
    "resilience",
    "sot_diff",
    "verification",
]
