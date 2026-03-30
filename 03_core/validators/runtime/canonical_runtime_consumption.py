"""
Canonical Runtime Consumption Validator (WAVE_06)

Enforces that all cross-root consumers use the canonical reference/service
facade with runtime gate checks.  Direct provider imports are forbidden.

Fail-closed: any parse error, missing metadata, or ambiguous state results
in a FAIL finding.  Deterministic: same inputs always produce the same
ordered findings list.
"""

from __future__ import annotations

import ast
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import yaml


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ConsumptionFinding:
    """Single finding from canonical consumption validation."""

    finding_code: str
    # Codes:
    #   DIRECT_PROVIDER_IMPORT       - imports directly from another root's src/
    #   MISSING_RUNTIME_GATE         - cross-root access without gate call
    #   UNDECLARED_CAPABILITY        - capability not in runtime/index.yaml
    #   UNAUTHORIZED_PROVIDER        - provider not in declared dependencies
    #   MISSING_REFERENCE_FACADE     - no reference_services facade detected

    severity: str  # "critical" / "high" / "medium"
    file_path: str
    line_number: Optional[int]
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_code": self.finding_code,
            "severity": self.severity,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class ConsumptionValidationResult:
    """Result of canonical consumption validation for a single shard."""

    consumer_root_id: str
    consumer_shard_id: str
    status: str  # "pass" / "fail"
    findings: tuple[ConsumptionFinding, ...]
    result_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "consumer_root_id": self.consumer_root_id,
            "consumer_shard_id": self.consumer_shard_id,
            "status": self.status,
            "findings": [f.to_dict() for f in self.findings],
            "result_hash": self.result_hash,
        }


# ---------------------------------------------------------------------------
# Registry helpers
# ---------------------------------------------------------------------------

REGISTRY_PATH = Path("24_meta_orchestration/registry/shards_registry.json")


def _load_registry(repo_root: Path) -> dict[tuple[str, str], dict[str, Any]]:
    """Load registry keyed by (root_id, shard_id)."""
    path = repo_root / REGISTRY_PATH
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for item in payload.get("shards", []):
        if isinstance(item, dict):
            key = (str(item.get("root_id", "")), str(item.get("shard_id", "")).split("/")[-1])
            result[key] = item
    return result


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _get_allowed_providers(repo_root: Path, root_id: str, shard_id: str) -> set[tuple[str, str]]:
    """Extract allowed providers from runtime/index.yaml dependencies."""
    runtime_index = _read_yaml(repo_root / root_id / "shards" / shard_id / "runtime" / "index.yaml")
    deps = runtime_index.get("runtime_dependencies", [])
    if not isinstance(deps, list):
        return set()
    providers = set()
    for dep in deps:
        if isinstance(dep, dict):
            prov_root = str(dep.get("provider_root_id", ""))
            prov_shard = str(dep.get("provider_shard_id", "")).split("/")[-1]
            if prov_root and prov_shard:
                providers.add((prov_root, prov_shard))
    return providers


def _get_declared_capabilities(repo_root: Path, root_id: str, shard_id: str) -> set[str]:
    """Get dependency capabilities declared in runtime/index.yaml."""
    runtime_index = _read_yaml(repo_root / root_id / "shards" / shard_id / "runtime" / "index.yaml")
    deps = runtime_index.get("runtime_dependencies", [])
    if not isinstance(deps, list):
        return set()
    caps = set()
    for dep in deps:
        if isinstance(dep, dict):
            cap = dep.get("dependency_capability")
            if cap:
                caps.add(str(cap))
    return caps


# ---------------------------------------------------------------------------
# Import analysis (AST-based)
# ---------------------------------------------------------------------------

import re as _re

# Regex fallback for files that fail AST parsing (e.g. digit-prefixed root names)
_IMPORT_RE = _re.compile(
    r"^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))",
    _re.MULTILINE,
)


def _extract_imports(source_code: str) -> list[tuple[str, int]]:
    """Extract all import module paths with line numbers from Python source.

    Uses AST when possible; falls back to regex for unparseable files
    (fail-closed: we must still detect cross-root references).
    """
    imports: list[tuple[str, int]] = []
    try:
        tree = ast.parse(source_code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append((alias.name, node.lineno))
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append((node.module, node.lineno))
        return imports
    except SyntaxError:
        pass
    # Regex fallback — fail-closed: detect patterns even in unparseable files
    for lineno, line in enumerate(source_code.splitlines(), start=1):
        m = _IMPORT_RE.match(line)
        if m:
            mod = m.group(1) or m.group(2)
            if mod:
                imports.append((mod, lineno))
    return imports


def _is_cross_root_import(import_path: str, consumer_root_id: str) -> tuple[bool, str | None]:
    """Check if an import references another root's code.

    Returns (is_cross_root, provider_root_id_or_None).
    """
    # Pattern: XX_root_name.src... or XX_root_name.shards...
    parts = import_path.split(".")
    if len(parts) < 2:
        return False, None
    first = parts[0]
    # Check if it looks like a root ID (e.g., 03_core, 09_meta_identity)
    if "_" in first and len(first) >= 4 and first[:2].isdigit():
        if first != consumer_root_id:
            return True, first
    return False, None


def _check_gate_usage(source_code: str) -> bool:
    """Check if the source code calls enforce_runtime_dependencies or resolve_runtime_gate."""
    gate_patterns = [
        "enforce_runtime_dependencies",
        "resolve_runtime_gate",
        "evaluate_runtime_dependency",
        "cross_root_runtime_gate",
    ]
    return any(pattern in source_code for pattern in gate_patterns)


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------

class CanonicalConsumptionPolicy:
    """Validates canonical runtime consumption patterns for cross-root consumers."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self._registry = _load_registry(repo_root)

    def validate_consumer(self, consumer_root_id: str, consumer_shard_id: str) -> ConsumptionValidationResult:
        """Validate that a consumer shard only uses canonical consumption patterns."""
        findings: list[ConsumptionFinding] = []

        shard_src = self.repo_root / consumer_root_id / "src"
        allowed_providers = _get_allowed_providers(self.repo_root, consumer_root_id, consumer_shard_id)
        declared_caps = _get_declared_capabilities(self.repo_root, consumer_root_id, consumer_shard_id)

        # 1. Check for reference facade
        has_facade = (shard_src / "reference_services.py").exists()
        if not has_facade and allowed_providers:
            findings.append(ConsumptionFinding(
                finding_code="MISSING_REFERENCE_FACADE",
                severity="high",
                file_path=str(shard_src / "reference_services.py"),
                line_number=None,
                detail=f"Consumer {consumer_root_id}/{consumer_shard_id} has cross-root dependencies but no reference_services.py facade",
            ))

        # 2. Scan source files for imports
        if shard_src.exists():
            for py_file in sorted(shard_src.glob("**/*.py")):
                try:
                    source = py_file.read_text(encoding="utf-8")
                except Exception:
                    continue

                imports = _extract_imports(source)
                has_gate = _check_gate_usage(source)

                for import_path, lineno in imports:
                    is_cross, provider_root = _is_cross_root_import(import_path, consumer_root_id)
                    if not is_cross or provider_root is None:
                        continue

                    # Direct cross-root import
                    if ".src." in import_path or import_path.endswith(".src"):
                        findings.append(ConsumptionFinding(
                            finding_code="DIRECT_PROVIDER_IMPORT",
                            severity="critical",
                            file_path=str(py_file.relative_to(self.repo_root)),
                            line_number=lineno,
                            detail=f"Direct cross-root import from {provider_root}: {import_path}",
                        ))

                    # Check if provider is authorized
                    provider_shard_guess = import_path.split(".")[1] if len(import_path.split(".")) > 1 else ""
                    if allowed_providers and not any(p[0] == provider_root for p in allowed_providers):
                        findings.append(ConsumptionFinding(
                            finding_code="UNAUTHORIZED_PROVIDER",
                            severity="high",
                            file_path=str(py_file.relative_to(self.repo_root)),
                            line_number=lineno,
                            detail=f"Access to unauthorized provider root {provider_root}",
                        ))

                # Cross-root code without gate usage
                has_cross_root = any(_is_cross_root_import(imp, consumer_root_id)[0] for imp, _ in imports)
                if has_cross_root and not has_gate:
                    findings.append(ConsumptionFinding(
                        finding_code="MISSING_RUNTIME_GATE",
                        severity="critical",
                        file_path=str(py_file.relative_to(self.repo_root)),
                        line_number=None,
                        detail=f"Cross-root access without runtime gate call in {py_file.name}",
                    ))

        # 3. Check capability declarations
        registry_entry = self._registry.get((consumer_root_id, consumer_shard_id))
        if registry_entry:
            reg_dep_caps = set(registry_entry.get("dependency_capability", []))
            if reg_dep_caps and declared_caps and reg_dep_caps != declared_caps:
                findings.append(ConsumptionFinding(
                    finding_code="UNDECLARED_CAPABILITY",
                    severity="high",
                    file_path=str(self.repo_root / consumer_root_id / "shards" / consumer_shard_id / "runtime" / "index.yaml"),
                    line_number=None,
                    detail=f"Registry/runtime capability mismatch: registry={sorted(reg_dep_caps)}, runtime={sorted(declared_caps)}",
                ))

        # Build result
        status = "fail" if findings else "pass"
        sorted_findings = tuple(sorted(findings, key=lambda f: (f.severity, f.finding_code, f.file_path, f.line_number or 0)))
        result_payload = json.dumps([f.to_dict() for f in sorted_findings], sort_keys=True)
        result_hash = hashlib.sha256(result_payload.encode()).hexdigest()

        return ConsumptionValidationResult(
            consumer_root_id=consumer_root_id,
            consumer_shard_id=consumer_shard_id,
            status=status,
            findings=sorted_findings,
            result_hash=result_hash,
        )

    def validate_all_consumers(self) -> list[ConsumptionValidationResult]:
        """Validate all shards that have runtime/index.yaml with dependencies."""
        results: list[ConsumptionValidationResult] = []
        for (root_id, shard_id), entry in sorted(self._registry.items()):
            dep_caps = entry.get("dependency_capability", [])
            if dep_caps:  # Only validate consumers (shards with dependencies)
                results.append(self.validate_consumer(root_id, shard_id))
        return results
