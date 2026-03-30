"""Identity resolution for ssidctl CLI.

Deterministic, local-only identity resolution:
1. ENV var SSID_IDENTITY (if set)
2. OS username (fallback)
3. Map to role via identities.yaml

No network calls. No OIDC. No secrets.
"""

from __future__ import annotations

import getpass
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

try:
    import jsonschema

    _HAS_JSONSCHEMA = True
except ImportError:
    _HAS_JSONSCHEMA = False


class IdentityError(Exception):
    """Raised when identity resolution fails."""


@dataclass(frozen=True)
class ResolvedIdentity:
    """Resolved identity with username, role, and source."""

    username: str
    role: str
    source: str  # "env", "os", "default"
    display_name: str = ""

    def is_privileged(self) -> bool:
        return self.role in ("owner", "admin")


# Default schema path (relative to SSID repo)
_SCHEMA_REL = Path("16_codex/contracts/ssidctl/identities.schema.json")


def resolve_username(env_var: str = "SSID_IDENTITY") -> tuple[str, str]:
    """Resolve the current username and source.

    Returns:
        (username, source) where source is "env" or "os".
    """
    env_val = os.environ.get(env_var, "").strip()
    if env_val:
        return env_val, "env"
    return getpass.getuser(), "os"


def load_identities(
    identities_path: Path,
    schema_path: Path | None = None,
) -> dict[str, Any]:
    """Load and validate identities.yaml.

    Args:
        identities_path: Path to identities.yaml.
        schema_path: Optional path to JSON schema for validation.

    Returns:
        Parsed identities dict.

    Raises:
        IdentityError: On file not found, parse error, or schema violation.
    """
    if not identities_path.exists():
        raise IdentityError(f"Identities file not found: {identities_path}")

    try:
        with open(identities_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise IdentityError(f"Identities YAML parse error: {e}") from e

    if not isinstance(data, dict):
        raise IdentityError("Identities file must be a YAML mapping")

    if "identities" not in data:
        raise IdentityError("Identities file must contain 'identities' key")

    # Schema validation (optional, if jsonschema available)
    if _HAS_JSONSCHEMA and schema_path and schema_path.exists():
        try:
            with open(schema_path, encoding="utf-8") as f:
                schema = json.load(f)
            jsonschema.validate(instance=data, schema=schema)
        except jsonschema.ValidationError as e:
            raise IdentityError(f"Identities schema validation failed: {e.message}") from e

    return data


def resolve_identity(
    identities_path: Path,
    env_var: str = "SSID_IDENTITY",
    default_role: str = "readonly",
    schema_path: Path | None = None,
) -> ResolvedIdentity:
    """Resolve the current user's identity and role.

    Resolution order:
    1. ENV var (SSID_IDENTITY) -> username
    2. OS username -> fallback
    3. Lookup in identities.yaml -> role
    4. If not found -> default_role

    Args:
        identities_path: Path to identities.yaml.
        env_var: ENV var name for identity override.
        default_role: Role for unknown users.
        schema_path: Optional JSON schema path for validation.

    Returns:
        ResolvedIdentity with username, role, source.
    """
    username, source = resolve_username(env_var)

    data = load_identities(identities_path, schema_path)
    identities = data.get("identities", {})
    file_default = data.get("default_role", default_role)

    entry = identities.get(username)
    if entry is not None:
        return ResolvedIdentity(
            username=username,
            role=entry["role"],
            source=source,
            display_name=entry.get("display_name", ""),
        )

    return ResolvedIdentity(
        username=username,
        role=file_default,
        source="default",
    )
