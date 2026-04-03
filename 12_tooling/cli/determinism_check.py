"""determinism_check — Verify deterministic behaviour of SSID artefacts.

Checks that generated files, JSON/YAML outputs, and build artefacts
are fully reproducible (same input -> same output). This tool is
designed to run in CI or locally as a gate before promotion.

Registry import path (orchestrator):
    12_tooling.cli.determinism_check
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class CheckResult:
    """Result of a single determinism check."""
    check_name: str
    passed: bool
    details: str = ""


@dataclass
class DeterminismReport:
    """Aggregated report of all determinism checks."""
    results: List[CheckResult] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all(r.passed for r in self.results)

    def summary(self) -> str:
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        failed = total - passed
        lines = [f"Determinism Report: {passed}/{total} passed, {failed} failed"]
        for r in self.results:
            status = "PASS" if r.passed else "FAIL"
            lines.append(f"  [{status}] {r.check_name}: {r.details}")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "all_passed": self.all_passed,
            "results": sorted(
                [
                    {
                        "check_name": r.check_name,
                        "details": r.details,
                        "passed": r.passed,
                    }
                    for r in self.results
                ],
                key=lambda x: x["check_name"],
            ),
        }


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

# Patterns that indicate non-deterministic timestamps embedded in files.
# Matches ISO-8601 with sub-second precision that varies across runs.
_VOLATILE_TIMESTAMP_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z?"
)

# Patterns indicating seed-free randomness usage.
_RANDOM_IMPORT_RE = re.compile(
    r"(?:^|\s)(?:import\s+random|from\s+random\s+import)"
)
_RANDOM_CALL_NO_SEED_RE = re.compile(
    r"random\.(random|randint|choice|sample|shuffle|uniform)\s*\("
)
_SEED_CALL_RE = re.compile(r"random\.seed\s*\(")


def check_no_volatile_timestamps(
    paths: Sequence[Path],
    *,
    allowed_files: Optional[Sequence[str]] = None,
) -> CheckResult:
    """Check that generated files do not contain volatile sub-second timestamps.

    Files whose names match *allowed_files* patterns are skipped.
    """
    allowed = set(allowed_files or [])
    violations: List[str] = []

    for path in sorted(paths):
        if path.name in allowed:
            continue
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        matches = _VOLATILE_TIMESTAMP_RE.findall(text)
        if matches:
            violations.append(f"{path}: {len(matches)} volatile timestamp(s)")

    if violations:
        return CheckResult(
            check_name="no_volatile_timestamps",
            passed=False,
            details="; ".join(violations[:10]),
        )
    return CheckResult(
        check_name="no_volatile_timestamps",
        passed=True,
        details=f"Checked {len(paths)} file(s), no volatile timestamps found",
    )


def check_json_sorted(paths: Sequence[Path]) -> CheckResult:
    """Check that JSON files have sorted keys."""
    violations: List[str] = []

    for path in sorted(paths):
        if not path.is_file() or path.suffix.lower() != ".json":
            continue
        try:
            text = path.read_text(encoding="utf-8")
            data = json.loads(text)
        except (OSError, json.JSONDecodeError):
            continue
        canonical = json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False)
        reparsed = json.dumps(json.loads(text), sort_keys=False, indent=2, ensure_ascii=False)
        # Compare the key order: re-serialize with sort_keys and compare
        if json.dumps(data, sort_keys=True) != json.dumps(data, sort_keys=False):
            violations.append(str(path))

    if violations:
        return CheckResult(
            check_name="json_sorted_keys",
            passed=False,
            details=f"Unsorted JSON: {', '.join(str(v) for v in violations[:10])}",
        )
    return CheckResult(
        check_name="json_sorted_keys",
        passed=True,
        details=f"All checked JSON files have sorted keys",
    )


def check_yaml_sorted(paths: Sequence[Path]) -> CheckResult:
    """Check that YAML files have sorted top-level keys.

    Only checks files with .yaml or .yml extension. Requires PyYAML;
    if unavailable the check is skipped with a pass.
    """
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        return CheckResult(
            check_name="yaml_sorted_keys",
            passed=True,
            details="PyYAML not available, skipped",
        )

    violations: List[str] = []
    for path in sorted(paths):
        if not path.is_file():
            continue
        if path.suffix.lower() not in (".yaml", ".yml"):
            continue
        try:
            text = path.read_text(encoding="utf-8")
            data = yaml.safe_load(text)
        except (OSError, yaml.YAMLError):
            continue
        if isinstance(data, dict):
            keys = list(data.keys())
            if keys != sorted(keys):
                violations.append(str(path))

    if violations:
        return CheckResult(
            check_name="yaml_sorted_keys",
            passed=False,
            details=f"Unsorted YAML: {', '.join(violations[:10])}",
        )
    return CheckResult(
        check_name="yaml_sorted_keys",
        passed=True,
        details="All checked YAML files have sorted top-level keys",
    )


def check_no_seedless_random(paths: Sequence[Path]) -> CheckResult:
    """Check that Python files do not use random without seeding.

    Any file that imports ``random`` and calls random functions
    must also contain a ``random.seed(...)`` call.
    """
    violations: List[str] = []

    for path in sorted(paths):
        if not path.is_file() or path.suffix.lower() != ".py":
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if not _RANDOM_IMPORT_RE.search(text):
            continue
        if _RANDOM_CALL_NO_SEED_RE.search(text) and not _SEED_CALL_RE.search(text):
            violations.append(str(path))

    if violations:
        return CheckResult(
            check_name="no_seedless_random",
            passed=False,
            details=f"Seedless random usage: {', '.join(violations[:10])}",
        )
    return CheckResult(
        check_name="no_seedless_random",
        passed=True,
        details=f"Checked {len(paths)} file(s), no unseeded random found",
    )


def check_build_artifact_hash_stability(
    artifact_paths: Sequence[Path],
    expected_hashes: Optional[Dict[str, str]] = None,
) -> CheckResult:
    """Check that build artefacts produce stable SHA-256 hashes.

    If *expected_hashes* is provided (mapping filename -> hex digest),
    each artefact is verified against its expected hash. Otherwise,
    the check simply confirms all artefacts are hashable and records
    their hashes.
    """
    computed: Dict[str, str] = {}
    errors: List[str] = []

    for path in sorted(artifact_paths):
        if not path.is_file():
            errors.append(f"{path}: not found")
            continue
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        computed[path.name] = sha

    if expected_hashes:
        for name, expected in sorted(expected_hashes.items()):
            actual = computed.get(name)
            if actual is None:
                errors.append(f"{name}: missing artefact")
            elif actual != expected:
                errors.append(
                    f"{name}: hash mismatch (expected {expected[:12]}..., "
                    f"got {actual[:12]}...)"
                )

    if errors:
        return CheckResult(
            check_name="build_artifact_hash_stability",
            passed=False,
            details="; ".join(errors[:10]),
        )
    return CheckResult(
        check_name="build_artifact_hash_stability",
        passed=True,
        details=f"Verified {len(computed)} artefact(s)",
    )


# ---------------------------------------------------------------------------
# Aggregated runner
# ---------------------------------------------------------------------------

def run_all_checks(
    scan_root: Path,
    *,
    artifact_paths: Optional[Sequence[Path]] = None,
    expected_hashes: Optional[Dict[str, str]] = None,
    allowed_timestamp_files: Optional[Sequence[str]] = None,
) -> DeterminismReport:
    """Run all determinism checks under *scan_root*.

    Args:
        scan_root: Directory to scan for generated files.
        artifact_paths: Explicit list of build artefact paths to hash-check.
        expected_hashes: Optional mapping of artefact filename -> SHA-256.
        allowed_timestamp_files: Filenames exempt from timestamp check.

    Returns:
        A ``DeterminismReport`` with individual check results.
    """
    all_files = sorted(scan_root.rglob("*")) if scan_root.is_dir() else []
    py_files = [f for f in all_files if f.suffix == ".py"]
    json_files = [f for f in all_files if f.suffix == ".json"]
    yaml_files = [f for f in all_files if f.suffix in (".yaml", ".yml")]

    report = DeterminismReport()
    report.results.append(
        check_no_volatile_timestamps(
            all_files, allowed_files=allowed_timestamp_files
        )
    )
    report.results.append(check_json_sorted(json_files))
    report.results.append(check_yaml_sorted(yaml_files))
    report.results.append(check_no_seedless_random(py_files))
    report.results.append(
        check_build_artifact_hash_stability(
            list(artifact_paths or []),
            expected_hashes=expected_hashes,
        )
    )
    return report


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point for determinism checks.

    Usage:
        python -m determinism_check [scan_root]
    """
    args = argv if argv is not None else sys.argv[1:]
    scan_root = Path(args[0]) if args else Path(".")

    if not scan_root.is_dir():
        print(f"Error: {scan_root} is not a directory", file=sys.stderr)
        return 1

    report = run_all_checks(scan_root)
    print(report.summary())
    return 0 if report.all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CheckResult",
    "DeterminismReport",
    "check_build_artifact_hash_stability",
    "check_json_sorted",
    "check_no_seedless_random",
    "check_no_volatile_timestamps",
    "check_yaml_sorted",
    "run_all_checks",
]
