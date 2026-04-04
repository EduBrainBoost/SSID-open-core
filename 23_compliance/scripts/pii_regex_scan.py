#!/usr/bin/env python3
"""AR-01: pii_regex_scan.py
Scan files for PII using regex patterns from pii_patterns.yaml.
Outputs findings per file in JSON format.
Exits 0 if no PII found (PASS); exits 1 if PII found (FAIL_POLICY).
"""

import argparse
import hashlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

try:
    import yaml

    HAS_YAML = True
except ImportError:
    HAS_YAML = False

DEFAULT_PATTERNS_PATH = Path(__file__).parent.parent / "rules" / "pii_patterns.yaml"


def load_patterns(patterns_path: Path) -> tuple[list[dict], list[dict]]:
    """Load PII patterns and exclusion rules from YAML."""
    if not HAS_YAML:
        raise RuntimeError("PyYAML required: pip install pyyaml")
    config = yaml.safe_load(patterns_path.read_text(encoding="utf-8"))
    return config.get("patterns", []), config.get("exclusions", [])


def is_excluded(match_str: str, line: str, exclusions: list[dict]) -> bool:
    """Return True if this match should be excluded as false positive."""
    return any(re.search(excl["pattern"], match_str) or re.search(excl["pattern"], line) for excl in exclusions)


def scan_file(
    file_path: Path,
    patterns: list[dict],
    exclusions: list[dict],
) -> dict:
    """Scan a single file for PII patterns. Returns per-file findings dict."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        sha256 = hashlib.sha256(file_path.read_bytes()).hexdigest()
    except OSError as e:
        return {
            "file": str(file_path),
            "sha256": "",
            "result": "ERROR",
            "error": str(e),
            "findings": [],
        }

    findings = []
    for pattern_def in patterns:
        pid = pattern_def["id"]
        regex = pattern_def["regex"]
        severity = pattern_def.get("severity", "MEDIUM")
        try:
            compiled = re.compile(regex)
        except re.error:
            continue

        for line_no, line in enumerate(content.splitlines(), 1):
            for match in compiled.finditer(line):
                match_str = match.group(0)
                if is_excluded(match_str, line, exclusions):
                    continue
                findings.append(
                    {
                        "pattern_id": pid,
                        "severity": severity,
                        "line": line_no,
                        "match_length": len(match_str),
                        # Never store the actual PII value — only length + position
                        "col_start": match.start(),
                    }
                )

    result_status = "PASS" if not findings else "FAIL_POLICY"
    return {
        "file": str(file_path),
        "sha256": sha256,
        "result": result_status,
        "findings": len(findings),
        "check": "pii_regex",
        "pattern_findings": findings,
    }


def collect_files(files_arg: list[str], repo_root: Path) -> list[Path]:
    """Expand file list from CLI arg (supports glob patterns and literal paths)."""
    paths = []
    for f in files_arg:
        p = Path(f)
        if not p.is_absolute():
            p = repo_root / p
        if p.exists():
            paths.append(p)
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description="PII regex scanner (AR-01)")
    parser.add_argument(
        "--files",
        nargs="+",
        required=True,
        help="Files to scan (space-separated paths)",
    )
    parser.add_argument(
        "--patterns",
        default=str(DEFAULT_PATTERNS_PATH),
        help="Path to pii_patterns.yaml",
    )
    parser.add_argument("--out", required=True, help="Output JSON path")
    parser.add_argument("--repo-root", default=".", help="Repo root for relative paths")
    parser.add_argument("--ems-url", default="", help="EMS base URL for result reporting (optional)")
    parser.add_argument("--run-id", default="", help="Run ID for EMS reporting")
    parser.add_argument("--commit-sha", default="0" * 40, help="Commit SHA for EMS reporting")
    args = parser.parse_args()

    repo_root = Path(args.repo_root)
    patterns, exclusions = load_patterns(Path(args.patterns))
    files = collect_files(args.files, repo_root)

    results = []
    total_findings = 0

    for fp in files:
        file_result = scan_file(fp, patterns, exclusions)
        results.append(file_result)
        total_findings += file_result.get("findings", 0)

    overall_status = "PASS" if total_findings == 0 else "FAIL_POLICY"
    output = {
        "status": overall_status,
        "total_files_scanned": len(files),
        "total_findings": total_findings,
        "ts": datetime.now(UTC).isoformat(),
        "files": results,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2))
    print(f"PII scan: {len(files)} files, {total_findings} findings, status={overall_status}")

    if args.ems_url:
        try:
            import os as _os
            import sys as _sys

            _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "..", "12_tooling"))
            from datetime import datetime as _dt

            from ssid_autorunner.ems_reporter import post_result

            post_result(
                ems_url=args.ems_url,
                ar_id="AR-01",
                run_id=args.run_id or f"CI-AR-01-{_dt.now(UTC).strftime('%Y%m%dT%H%M%S')}",
                result=output,
                commit_sha=args.commit_sha,
            )
        except (ImportError, Exception):
            pass  # ems_reporter optional — never block the gate

    sys.exit(0 if overall_status == "PASS" else 1)


if __name__ == "__main__":
    main()
