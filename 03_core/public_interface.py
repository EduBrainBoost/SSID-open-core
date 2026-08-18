"""OpenCore public SDK — core interfaces."""
from __future__ import annotations


class PublicInterface:
    """Base public interface for all OpenCore modules."""

    version: str = "1.0.0"
    scope: str = "public"

    def validate(self) -> dict:
        """Validate this interface's contract."""
        return {
            "version": self.version,
            "scope": self.scope,
            "valid": True,
        }


class SchemaContract(PublicInterface):
    """Public schema contract for data interchange."""

    def __init__(self, schema_name: str, schema_version: str = "1.0.0") -> None:
        self.schema_name = schema_name
        self.schema_version = schema_version

    def to_dict(self) -> dict:
        return {
            "name": self.schema_name,
            "version": self.schema_version,
            "type": "public_schema",
        }


class AdapterContract(PublicInterface):
    """Public adapter contract for external integrations."""

    def __init__(self, adapter_name: str, backend: str = "mock") -> None:
        self.adapter_name = adapter_name
        self.backend = backend

    def is_public(self) -> bool:
        return self.backend in ("mock", "reference", "public")

    def to_dict(self) -> dict:
        return {
            "name": self.adapter_name,
            "backend": self.backend,
            "public": self.is_public(),
        }
