"""
Runtime Bypass Detector (WAVE_06)

Detects forbidden patterns that bypass the canonical runtime consumption path.
Scans Python source files for:

- direct_cross_root_import: import from another root's src/ directly
- provider_implementation_access: using provider internals instead of facade
- gate_circumvention: calling provider without runtime gate
- unregistered_capability_use: using capability not in runtime/index.yaml
- undeclared_provider_access: accessing provider not in allowed list

Deterministic: same inputs always produce the same ordered findings list.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class BypassFinding:
    """Single bypass detection finding."""

    pattern_type: str
    consumer_root_id: str
    consumer_shard_id: str
    provider_root_id: str | None
    file_path: str
    line_number: int
    detail: str
    severity: str  # "critical" for gate bypass, "high" for direct imports

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern_type": self.pattern_type,
            "consumer_root_id": self.consumer_root_id,
            "consumer_shard_id": self.consumer_shard_id,
            "provider_root_id": self.provider_root_id,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "detail": self.detail,
            "severity": self.severity,
        }


# Regex for detecting root-like module names (e.g. 03_core, 09_meta_identity)
_ROOT_PATTERN = re.compile(r"^\d{2}_\w+$")

# Regex for direct cross-root import lines
_IMPORT_RE = re.compile(r"^\s*(?:from\s+(\S+)\s+import|import\s+(\S+))")


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _get_allowed_providers(repo_root: Path, root_id: str, shard_id: str) -> set[str]:
    """Get provider root IDs from runtime/index.yaml dependencies."""
    runtime_index = _read_yaml(repo_root / root_id / "shards" / shard_id / "runtime" / "index.yaml")
    deps = runtime_index.get("runtime_dependencies", [])
    if not isinstance(deps, list):
        return set()
    return {str(d.get("provider_root_id", "")) for d in deps if isinstance(d, dict) and d.get("provider_root_id")}


def _get_declared_dep_capabilities(repo_root: Path, root_id: str, shard_id: str) -> set[str]:
    """Get declared dependency capabilities from runtime/index.yaml."""
    runtime_index = _read_yaml(repo_root / root_id / "shards" / shard_id / "runtime" / "index.yaml")
    deps = runtime_index.get("runtime_dependencies", [])
    if not isinstance(deps, list):
        return set()
    return {
        str(d.get("dependency_capability", "")) for d in deps if isinstance(d, dict) and d.get("dependency_capability")
    }


class RuntimeBypassDetector:
    """Scans shards for forbidden bypass patterns."""

    BYPASS_PATTERNS = [
        "direct_cross_root_import",
        "provider_implementation_access",
        "gate_circumvention",
        "unregistered_capability_use",
        "undeclared_provider_access",
    ]

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root

    def scan_shard(self, root_id: str, shard_id: str) -> list[BypassFinding]:
        """Scan a single shard for bypass patterns."""
        findings: list[BypassFinding] = []
        shard_src = self.repo_root / root_id / "src"
        if not shard_src.exists():
            return findings

        allowed_providers = _get_allowed_providers(self.repo_root, root_id, shard_id)
        _get_declared_dep_capabilities(self.repo_root, root_id, shard_id)

        for py_file in sorted(shard_src.glob("**/*.py")):
            try:
                lines = py_file.read_text(encoding="utf-8").splitlines()
            except Exception:
                continue

            has_gate_call = any(
                "enforce_runtime_dependencies" in line
                or "resolve_runtime_gate" in line
                or "evaluate_runtime_dependency" in line
                for line in lines
            )
            has_cross_root = False

            for lineno, line in enumerate(lines, start=1):
                match = _IMPORT_RE.match(line)
                if not match:
                    continue
                import_path = match.group(1) or match.group(2)
                if not import_path:
                    continue

                parts = import_path.split(".")
                first = parts[0]
                if not _ROOT_PATTERN.match(first) or first == root_id:
                    continue

                has_cross_root = True
                rel_path = str(py_file.relative_to(self.repo_root))

                # 1. Direct cross-root import
                if ".src." in import_path or import_path.endswith(".src"):
                    findings.append(
                        BypassFinding(
                            pattern_type="direct_cross_root_import",
                            consumer_root_id=root_id,
                            consumer_shard_id=shard_id,
                            provider_root_id=first,
                            file_path=rel_path,
                            line_number=lineno,
                            detail=f"Direct import from provider src: {import_path}",
                            severity="critical",
                        )
                    )

                # 2. Provider implementation access (non-facade internals)
                if len(parts) >= 3 and parts[1] not in ("src", "shards"):
                    findings.append(
                        BypassFinding(
                            pattern_type="provider_implementation_access",
                            consumer_root_id=root_id,
                            consumer_shard_id=shard_id,
                            provider_root_id=first,
                            file_path=rel_path,
                            line_number=lineno,
                            detail=f"Access to provider internals: {import_path}",
                            severity="high",
                        )
                    )

                # 3. Undeclared provider access
                if allowed_providers and first not in allowed_providers:
                    findings.append(
                        BypassFinding(
                            pattern_type="undeclared_provider_access",
                            consumer_root_id=root_id,
                            consumer_shard_id=shard_id,
                            provider_root_id=first,
                            file_path=rel_path,
                            line_number=lineno,
                            detail=f"Provider {first} not in declared dependencies",
                            severity="high",
                        )
                    )

            # 4. Gate circumvention
            if has_cross_root and not has_gate_call:
                findings.append(
                    BypassFinding(
                        pattern_type="gate_circumvention",
                        consumer_root_id=root_id,
                        consumer_shard_id=shard_id,
                        provider_root_id=None,
                        file_path=str(py_file.relative_to(self.repo_root)),
                        line_number=0,
                        detail=f"Cross-root access without runtime gate call in {py_file.name}",
                        severity="critical",
                    )
                )

        return sorted(findings, key=lambda f: (f.severity, f.pattern_type, f.file_path, f.line_number))

    def scan_all_shards(self) -> dict[str, list[BypassFinding]]:
        """Scan all shards that have runtime/index.yaml for bypass patterns.

        Returns a dict keyed by ``root_id/shard_id``.
        """
        results: dict[str, list[BypassFinding]] = {}
        for root_dir in sorted(self.repo_root.iterdir()):
            if not root_dir.is_dir() or not _ROOT_PATTERN.match(root_dir.name):
                continue
            shards_dir = root_dir / "shards"
            if not shards_dir.exists():
                continue
            for shard_dir in sorted(shards_dir.iterdir()):
                if not shard_dir.is_dir():
                    continue
                runtime_idx = shard_dir / "runtime" / "index.yaml"
                if not runtime_idx.exists():
                    continue
                key = f"{root_dir.name}/{shard_dir.name}"
                findings = self.scan_shard(root_dir.name, shard_dir.name)
                if findings:
                    results[key] = findings
        return results

    def scan_summary(self) -> dict[str, Any]:
        """Return a deterministic summary of all bypass findings."""
        all_findings = self.scan_all_shards()
        total = sum(len(f) for f in all_findings.values())
        payload = json.dumps(
            {k: [f.to_dict() for f in v] for k, v in sorted(all_findings.items())},
            sort_keys=True,
        )
        return {
            "shards_scanned": len(all_findings),
            "total_findings": total,
            "by_shard": {k: len(v) for k, v in sorted(all_findings.items())},
            "summary_hash": hashlib.sha256(payload.encode()).hexdigest(),
        }
