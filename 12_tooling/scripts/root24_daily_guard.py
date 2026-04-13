#!/usr/bin/env python3
"""
Root24 Daily Guard — enforces ROOT-24-LOCK and security invariants.

Checks:
  1. Exactly 24 canonical root directories exist
  2. No forbidden root-level files (only allowlisted exceptions)
  3. No __pycache__ or .pytest_cache tracked in git
  4. registry.yaml.lock hash matches registry.yaml
  5. hash_chain.json is non-empty

Exit 0 on PASS, Exit 1 on FAIL.
Outputs JSON findings to stdout.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

CANONICAL_ROOTS = [
    "01_ai_layer",
    "02_audit_logging",
    "03_core",
    "04_deployment",
    "05_documentation",
    "06_data_pipeline",
    "07_governance_legal",
    "08_identity_score",
    "09_meta_identity",
    "10_interoperability",
    "11_test_simulation",
    "12_tooling",
    "13_ui_layer",
    "14_zero_time_auth",
    "15_infra",
    "16_codex",
    "17_observability",
    "18_data_layer",
    "19_adapters",
    "20_foundation",
    "21_post_quantum_crypto",
    "22_datasets",
    "23_compliance",
    "24_meta_orchestration",
]

ALLOWED_ROOT_FILES = {
    "CHANGELOG.md",
    "CLAUDE.md",
    "CONTRIBUTING.md",
    "DCO.txt",
    "LICENSE",
    "README.md",
    "SECURITY.md",
    "__init__.py",
    "conftest.py",
    "pyproject.toml",
    "pytest.ini",
    "requirements.lock",
    ".gitignore",
    ".mailmap",
    ".gitattributes",
    ".pre-commit-config.yaml",
}

ALLOWED_ROOT_DIRS = {
    ".github",
    ".ssid-system",
    "docs",
    ".git",
    "tasks",
}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _git_ls_files(repo: Path, pattern: str) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "ls-files", "--", pattern],
            capture_output=True,
            text=True,
            cwd=str(repo),
        )
        return [l for l in result.stdout.strip().splitlines() if l]
    except Exception:
        return []


def run_guard(repo_root: Path | None = None) -> dict:
    """Run all guard checks. Returns dict with 'status' and 'findings'."""
    if repo_root is None:
        repo_root = Path(__file__).resolve().parent.parent.parent

    findings: list[dict] = []
    overall_pass = True

    # --- Check 1: Exactly 24 canonical roots ---
    ignored_dirs = ALLOWED_ROOT_DIRS | {"__pycache__", ".pytest_cache", "node_modules"}
    existing_dirs = sorted(
        d.name
        for d in repo_root.iterdir()
        if d.is_dir() and d.name not in ignored_dirs and not d.name.startswith(".")
    )
    canonical_set = set(CANONICAL_ROOTS)
    existing_set = set(existing_dirs)

    missing = canonical_set - existing_set
    extra = existing_set - canonical_set

    if missing:
        findings.append({"check": "root24_missing", "severity": "FAIL", "details": sorted(missing)})
        overall_pass = False
    if extra:
        findings.append({"check": "root24_extra_dirs", "severity": "FAIL", "details": sorted(extra)})
        overall_pass = False
    if not missing and not extra:
        findings.append({"check": "root24_count", "severity": "PASS", "details": f"{len(existing_set)} roots OK"})

    # --- Check 2: No forbidden root-level files ---
    root_files = [
        f.name
        for f in repo_root.iterdir()
        if f.is_file() and f.name not in ALLOWED_ROOT_FILES and not f.name.startswith(".")
    ]
    if root_files:
        findings.append({"check": "forbidden_root_files", "severity": "FAIL", "details": sorted(root_files)})
        overall_pass = False
    else:
        findings.append({"check": "forbidden_root_files", "severity": "PASS", "details": "none"})

    # --- Check 3: No __pycache__ or .pytest_cache in git ---
    pycache_files = _git_ls_files(repo_root, "*__pycache__*")
    pytest_cache_files = _git_ls_files(repo_root, "*.pytest_cache*")
    cache_tracked = pycache_files + pytest_cache_files
    if cache_tracked:
        findings.append({"check": "cache_in_git", "severity": "FAIL", "details": cache_tracked[:20]})
        overall_pass = False
    else:
        findings.append({"check": "cache_in_git", "severity": "PASS", "details": "none tracked"})

    # --- Check 4: registry.yaml.lock hash match ---
    registry_yaml = repo_root / "24_meta_orchestration" / "registry" / "registry.yaml"
    registry_lock = repo_root / "24_meta_orchestration" / "registry" / "registry.yaml.lock"

    if registry_yaml.exists() and registry_lock.exists():
        yaml_hash = _sha256(registry_yaml)
        lock_content = registry_lock.read_text(encoding="utf-8").strip()
        # Lock file may contain just the hash or a structured format
        if yaml_hash in lock_content:
            findings.append({"check": "registry_lock_hash", "severity": "PASS", "details": "hash match"})
        else:
            findings.append({
                "check": "registry_lock_hash",
                "severity": "FAIL",
                "details": f"yaml_hash={yaml_hash[:16]}... not found in lock",
            })
            overall_pass = False
    elif not registry_yaml.exists():
        findings.append({"check": "registry_lock_hash", "severity": "WARN", "details": "registry.yaml missing"})
    elif not registry_lock.exists():
        findings.append({"check": "registry_lock_hash", "severity": "WARN", "details": "registry.yaml.lock missing"})

    # --- Check 5: hash_chain.json not empty ---
    hash_chain = repo_root / "24_meta_orchestration" / "registry" / "locks" / "hash_chain.json"
    if hash_chain.exists():
        content = hash_chain.read_text(encoding="utf-8").strip()
        if len(content) > 2:  # more than just "{}" or "[]"
            findings.append({"check": "hash_chain_nonempty", "severity": "PASS", "details": f"{len(content)} bytes"})
        else:
            findings.append({"check": "hash_chain_nonempty", "severity": "FAIL", "details": "hash_chain.json is empty or trivial"})
            overall_pass = False
    else:
        findings.append({"check": "hash_chain_nonempty", "severity": "WARN", "details": "hash_chain.json not found"})

    return {
        "status": "PASS" if overall_pass else "FAIL",
        "findings": findings,
    }


def main() -> int:
    result = run_guard()
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
