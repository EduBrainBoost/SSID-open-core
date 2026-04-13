#!/usr/bin/env python3
"""SoT Sync Guard — CC-SSID-SOT-GUARD-01.

Change-impact analysis and drift prevention guard for the 9 SoT (Source of
Truth) artifacts.  Wraps the cross-artifact reference audit with:

  1.  Changed-artifact detection   (git diff or explicit --changed flag)
  2.  Impact-matrix expansion      (which peers must be checked)
  3.  Hash-drift detection         (sot_registry.json staleness)
  4.  Sync-plan generation         (human-readable, NO auto-fix)
  5.  JSON + Markdown report output

Designed for CI gate usage: deterministic exit codes, machine-readable
output, zero side-effects.

Exit codes:
  0 = PASS   — fully consistent, no drift
  1 = WARN   — advisory warnings only
  2 = FAIL   — hard consistency violations (hash drift, broken refs)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Import from cross_artifact_reference_audit (same directory)
# ---------------------------------------------------------------------------
_cli_dir = str(Path(__file__).resolve().parent)
if _cli_dir not in sys.path:
    sys.path.insert(0, _cli_dir)

from cross_artifact_reference_audit import (  # noqa: E402
    SOT_ARTIFACTS,
    AuditResult,
    Finding,
    sha256_file,
)
from cross_artifact_reference_audit import (
    run_audit as run_xref_audit,
)

EXIT_PASS = 0
EXIT_WARN = 1
EXIT_FAIL = 2

# ---------------------------------------------------------------------------
# Impact matrix: when artifact X changes, which artifacts MUST be checked?
# ---------------------------------------------------------------------------
SYNC_TARGETS: dict[str, list[str]] = {
    "contract": ["rego", "validator_core", "tests", "moscow_report"],
    "rego": ["contract", "validator_core"],
    "validator_core": ["contract", "tests"],
    "validator_cli": ["validator_core"],
    "tests": ["contract", "validator_core"],
    "moscow_report": ["contract"],
    "sot_registry": [],  # hash check only
    "workflow": [],  # target existence check only
    "diff_alert": ["sot_registry"],
}

# Human-readable action descriptions per artifact type
_SYNC_ACTION_DESCRIPTIONS: dict[str, str] = {
    "contract": "verify rule definitions match source contract",
    "rego": "verify deny clauses match contract rules",
    "validator_core": "verify RULES dict matches contract",
    "validator_cli": "verify CLI wrapper references correct validator_core API",
    "tests": "verify test coverage includes all contract rules",
    "moscow_report": "verify enforcement report lists all contract rules",
    "sot_registry": "verify registry hashes are up-to-date",
    "workflow": "verify workflow script targets exist on disk",
    "diff_alert": "verify diff alert entries match registry",
}

# Reverse lookup: relative path -> artifact key
_PATH_TO_KEY: dict[str, str] = {v: k for k, v in SOT_ARTIFACTS.items()}


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------
def _detect_changed_files_git(repo: Path) -> list[str] | None:
    """Return list of changed file paths (relative to repo) via git.

    Returns None if git is unavailable or the command fails.
    """
    try:
        proc = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~1"],
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode != 0:
            return None
        return [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None


def _match_changed_to_artifacts(changed_files: list[str]) -> set[str]:
    """Map changed file paths to SOT artifact keys."""
    changed_keys: set[str] = set()
    for fpath in changed_files:
        # Normalise to forward slashes for comparison
        normalised = fpath.replace("\\", "/")
        if normalised in _PATH_TO_KEY:
            changed_keys.add(_PATH_TO_KEY[normalised])
    return changed_keys


# ---------------------------------------------------------------------------
# Hash-drift check
# ---------------------------------------------------------------------------
def _load_registry_hashes(repo: Path) -> dict[str, dict[str, str]]:
    """Load sot_registry.json and return {artifact_name: {path, hash_sha256}}.

    Returns empty dict on any error.
    """
    registry_path = repo / SOT_ARTIFACTS["sot_registry"]
    if not registry_path.exists():
        return {}
    try:
        data = json.loads(registry_path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    result: dict[str, dict[str, str]] = {}
    for artifact in data.get("roots", {}).get("sot_artifacts", []):
        name = artifact.get("name", "")
        if name:
            result[name] = {
                "path": artifact.get("path", ""),
                "hash_sha256": artifact.get("hash_sha256", ""),
            }
    return result


def check_hash_drift(
    repo: Path,
    changed_keys: set[str],
    result: AuditResult,
) -> list[dict[str, str]]:
    """Check whether sot_registry.json hashes are current for changed artifacts.

    Returns a list of hash-update entries needed for the sync plan.
    """
    registry_hashes = _load_registry_hashes(repo)
    hash_updates: list[dict[str, str]] = []

    if not registry_hashes:
        return hash_updates

    # Build a lookup: artifact key -> registry name
    # Registry names use underscored filenames (e.g. "sot_contract_yaml")
    key_to_registry_name: dict[str, str] = {}
    for reg_name, reg_info in registry_hashes.items():
        reg_path = reg_info.get("path", "").replace("\\", "/")
        if reg_path in _PATH_TO_KEY:
            key_to_registry_name[_PATH_TO_KEY[reg_path]] = reg_name

    registry_also_changed = "sot_registry" in changed_keys

    for key in changed_keys:
        if key == "sot_registry":
            continue  # skip self-reference
        rel_path = SOT_ARTIFACTS[key]
        full_path = repo / rel_path
        if not full_path.exists():
            continue

        reg_name = key_to_registry_name.get(key, "")
        if not reg_name:
            continue

        reg_info = registry_hashes.get(reg_name, {})
        stored_hash = reg_info.get("hash_sha256", "")
        if not stored_hash:
            continue

        actual_hash = sha256_file(full_path)
        if actual_hash != stored_hash:
            if not registry_also_changed:
                result.add(
                    Finding(
                        "hash_drift_unresolved",
                        "deny",
                        rel_path,
                        f"artifact '{key}' changed but sot_registry.json hash not updated",
                    )
                )
            hash_updates.append(
                {
                    "name": reg_name,
                    "path": rel_path,
                    "current_hash": stored_hash,
                    "actual_hash": actual_hash,
                }
            )

    return hash_updates


# ---------------------------------------------------------------------------
# Sync plan generation
# ---------------------------------------------------------------------------
def build_sync_plan(
    changed_keys: set[str],
    affected_keys: set[str],
    hash_updates: list[dict[str, str]],
) -> dict[str, Any]:
    """Build a sync plan describing what needs updating."""
    sync_actions: list[dict[str, str]] = []
    for target_key in sorted(affected_keys):
        action_desc = _SYNC_ACTION_DESCRIPTIONS.get(target_key, "verify consistency with changed artifacts")
        sync_actions.append(
            {
                "target": target_key,
                "action": action_desc,
            }
        )

    return {
        "changed_artifacts": sorted(changed_keys),
        "affected_artifacts": sorted(affected_keys),
        "sync_actions": sync_actions,
        "hash_updates_needed": hash_updates,
    }


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------
def generate_report(
    result: AuditResult,
    repo: Path,
    changed_keys: set[str],
    affected_keys: set[str],
    sync_plan: dict[str, Any] | None,
) -> dict[str, Any]:
    ts = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    report: dict[str, Any] = {
        "audit_type": "sot_sync_guard",
        "timestamp_utc": ts,
        "repo": str(repo),
        "overall": result.overall,
        "changed_artifacts": sorted(changed_keys),
        "affected_artifacts": sorted(affected_keys),
        "finding_count": len(result.findings),
        "deny_count": sum(1 for f in result.findings if f.severity == "deny"),
        "warn_count": sum(1 for f in result.findings if f.severity == "warn"),
        "evidence_hash": result.evidence_hash(),
        "findings": [f.to_dict() for f in result.findings],
    }
    if sync_plan is not None:
        report["sync_plan"] = sync_plan
    return report


def generate_markdown_report(
    report: dict[str, Any],
    sync_plan: dict[str, Any] | None,
) -> str:
    """Render a human-readable Markdown summary."""
    lines: list[str] = []
    lines.append("# SoT Sync Guard Report")
    lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Overall**: {report['overall']}")
    lines.append(f"- **Timestamp**: {report['timestamp_utc']}")
    lines.append(
        f"- **Findings**: {report['finding_count']} (deny={report['deny_count']}, warn={report['warn_count']})"
    )
    lines.append(f"- **Evidence Hash**: `{report['evidence_hash'][:16]}...`")
    lines.append("")

    # Changed Artifacts
    lines.append("## Changed Artifacts")
    lines.append("")
    changed = report.get("changed_artifacts", [])
    if changed:
        for key in changed:
            lines.append(f"- `{key}` ({SOT_ARTIFACTS.get(key, '?')})")
    else:
        lines.append("_No SoT artifacts detected in changeset (full audit run)._")
    lines.append("")

    # Affected Artifacts
    lines.append("## Affected Artifacts")
    lines.append("")
    affected = report.get("affected_artifacts", [])
    if affected:
        for key in affected:
            lines.append(f"- `{key}` ({SOT_ARTIFACTS.get(key, '?')})")
    else:
        lines.append("_No additional artifacts affected._")
    lines.append("")

    # Findings
    lines.append("## Findings")
    lines.append("")
    findings = report.get("findings", [])
    if findings:
        for f in findings:
            tag = "FAIL" if f["severity"] == "deny" else f["severity"].upper()
            lines.append(f"- **[{tag}]** `{f['class']}`: {f['path']}")
            lines.append(f"  - {f['detail']}")
    else:
        lines.append("_No findings._")
    lines.append("")

    # Sync Plan
    if sync_plan is not None:
        lines.append("## Sync Plan")
        lines.append("")
        actions = sync_plan.get("sync_actions", [])
        if actions:
            lines.append("### Actions Required")
            lines.append("")
            for action in actions:
                lines.append(f"- **{action['target']}**: {action['action']}")
            lines.append("")

        hash_updates = sync_plan.get("hash_updates_needed", [])
        if hash_updates:
            lines.append("### Hash Updates Needed")
            lines.append("")
            for hu in hash_updates:
                lines.append(f"- `{hu['name']}` ({hu['path']})")
                lines.append(f"  - Current: `{hu['current_hash'][:16]}...`")
                lines.append(f"  - Actual:  `{hu['actual_hash'][:16]}...`")
            lines.append("")

        if not actions and not hash_updates:
            lines.append("_No sync actions required._")
            lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API for programmatic usage
# ---------------------------------------------------------------------------
def run_guard(
    repo: Path,
    changed_files: list[str] | None = None,
    emit_sync_plan: bool = False,
) -> tuple[AuditResult, set[str], set[str], dict[str, Any] | None]:
    """Run the SoT sync guard and return (result, changed_keys, affected_keys, sync_plan).

    Parameters
    ----------
    repo : Path
        SSID repository root.
    changed_files : list[str] | None
        Changed file paths relative to repo.  If *None*, all artifacts are checked.
    emit_sync_plan : bool
        Whether to generate a sync plan.

    Returns
    -------
    tuple of (AuditResult, set[str], set[str], dict | None)
        Combined audit result, changed artifact keys, affected artifact keys,
        and optional sync plan.
    """
    if changed_files is not None:
        changed_keys = _match_changed_to_artifacts(changed_files)
    else:
        changed_keys = set(SOT_ARTIFACTS.keys())

    xref_result = run_xref_audit(repo)

    affected_keys: set[str] = set()
    for key in changed_keys:
        for target in SYNC_TARGETS.get(key, []):
            affected_keys.add(target)
    affected_keys -= changed_keys

    combined = AuditResult()
    combined.findings.extend(xref_result.findings)
    hash_updates = check_hash_drift(repo, changed_keys, combined)

    sync_plan: dict[str, Any] | None = None
    if emit_sync_plan:
        sync_plan = build_sync_plan(changed_keys, affected_keys, hash_updates)

    return combined, changed_keys, affected_keys, sync_plan


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="sot_sync_guard.py",
        description="SoT drift prevention guard — change-impact analysis for SSID's 9 SoT artifacts.",
    )
    parser.add_argument(
        "--repo",
        default=str(Path(__file__).resolve().parents[2]),
        help="SSID repository root (default: auto-detect from script location)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        default=True,
        help="run guard, report findings, exit with code (default behaviour)",
    )
    parser.add_argument(
        "--emit-sync-plan",
        action="store_true",
        default=False,
        help="also emit a sync plan listing what needs updating",
    )
    parser.add_argument(
        "--changed",
        default=None,
        help="comma-separated list of changed file paths (relative to repo); "
        "if omitted, detect via git diff --name-only HEAD~1",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="output JSON instead of human-readable",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="write reports to directory (default: 02_audit_logging/reports/)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo = Path(args.repo).resolve()

    # ----- 1. Detect changed artifacts -----
    if args.changed is not None:
        changed_files = [f.strip() for f in args.changed.split(",") if f.strip()]
    else:
        changed_files = _detect_changed_files_git(repo)

    if changed_files is not None:
        changed_keys = _match_changed_to_artifacts(changed_files)
    else:
        # git not available — treat as "all might have changed"
        changed_keys = set(SOT_ARTIFACTS.keys())

    # ----- 2. Run cross-artifact reference audit -----
    xref_result = run_xref_audit(repo)

    # ----- 3. Change-impact analysis -----
    affected_keys: set[str] = set()
    for key in changed_keys:
        for target in SYNC_TARGETS.get(key, []):
            affected_keys.add(target)
    # Remove self-references
    affected_keys -= changed_keys

    # ----- 4. Hash-drift check -----
    # Combine findings into a single AuditResult
    combined = AuditResult()
    combined.findings.extend(xref_result.findings)

    hash_updates = check_hash_drift(repo, changed_keys, combined)

    # ----- 5. Sync plan -----
    sync_plan: dict[str, Any] | None = None
    if args.emit_sync_plan:
        sync_plan = build_sync_plan(changed_keys, affected_keys, hash_updates)

    # ----- 6. Generate reports -----
    report = generate_report(combined, repo, changed_keys, affected_keys, sync_plan)

    # ----- 7. Output -----
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"SoT Sync Guard: {combined.overall}")
        print(f"  Changed:  {sorted(changed_keys) if changed_keys else '(none detected)'}")
        print(f"  Affected: {sorted(affected_keys) if affected_keys else '(none)'}")
        print(f"  Findings: {len(combined.findings)} (deny={report['deny_count']}, warn={report['warn_count']})")
        print(f"  Evidence Hash: {report['evidence_hash'][:16]}...")
        if combined.findings:
            print()
            for f in combined.findings:
                tag = "FAIL" if f.severity == "deny" else f.severity.upper()
                print(f"  [{tag}] {f.finding_class}: {f.path}")
                print(f"         {f.detail}")
        if sync_plan:
            actions = sync_plan.get("sync_actions", [])
            if actions:
                print()
                print("  Sync Plan:")
                for action in actions:
                    print(f"    - {action['target']}: {action['action']}")
            hash_upd = sync_plan.get("hash_updates_needed", [])
            if hash_upd:
                print()
                print("  Hash Updates Needed:")
                for hu in hash_upd:
                    print(f"    - {hu['name']}: {hu['current_hash'][:16]}... -> {hu['actual_hash'][:16]}...")

    # ----- 8. Write report files -----
    output_dir_str = args.output or str(repo / "02_audit_logging" / "reports")
    output_dir = Path(output_dir_str)
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "sot_sync_guard_report.json"
    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    md_content = generate_markdown_report(report, sync_plan)
    md_path = output_dir / "sot_sync_guard_report.md"
    md_path.write_text(md_content, encoding="utf-8")

    if not args.json:
        print(f"\n  Reports written to: {output_dir}")

    return combined.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
