#!/usr/bin/env python3
"""
Local zero-cost verification gateway for SSID-open-core.

This is the canonical verification path for SSID-open-core.
No GitHub runners, no cloud costs, no external dependencies.

Exit codes:
  0 = all checks PASS
  1 = at least one hard error detected
"""

import re
import subprocess
import sys
from pathlib import Path

import yaml


def check_ruff_lint() -> tuple[bool, list[str]]:
    """Check code style with ruff."""
    errors = []
    try:
        result = subprocess.run(["ruff", "check", "."], capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            errors.append(f"Ruff lint failed:\n{result.stdout}")
        return result.returncode == 0, errors
    except Exception as e:
        errors.append(f"Ruff lint check error: {e}")
        return False, errors


def check_ruff_format() -> tuple[bool, list[str]]:
    """Check code formatting with ruff."""
    errors = []
    try:
        result = subprocess.run(["ruff", "format", "--check", "."], capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            errors.append(f"Ruff format check failed:\n{result.stdout}")
        return result.returncode == 0, errors
    except Exception as e:
        errors.append(f"Ruff format check error: {e}")
        return False, errors


def check_module_yaml() -> tuple[bool, list[str]]:
    """Validate all module.yaml files."""
    errors = []
    REQUIRED_KEYS = {"module_id", "name", "version", "status"}

    modules = list(Path(".").glob("*/module.yaml"))
    if not modules:
        return True, ["No module.yaml files found (expected)"]

    for path in sorted(modules):
        try:
            with open(path) as f:
                data = yaml.safe_load(f)

            if not isinstance(data, dict):
                errors.append(f"{path}: not a valid YAML mapping")
                continue

            missing = REQUIRED_KEYS - set(data.keys())
            if missing:
                errors.append(f"{path}: missing required keys {missing}")
            else:
                print(f"PASS: {path} (module_id={data.get('module_id')})")
        except yaml.YAMLError as e:
            errors.append(f"{path}: YAML parse error: {e}")
        except Exception as e:
            errors.append(f"{path}: {e}")

    return len(errors) == 0, errors


def check_export_policy() -> tuple[bool, list[str]]:
    """Validate export policy YAML."""
    errors = []
    policy_path = Path("16_codex/opencore_export_policy.yaml")

    if not policy_path.exists():
        return False, [f"Export policy not found: {policy_path}"]

    try:
        with open(policy_path) as f:
            policy = yaml.safe_load(f)

        required = {
            "version",
            "source_repo",
            "target_repo",
            "mode",
            "allow_prefixes",
            "deny_roots",
            "deny_globs",
            "secret_scan_regex",
            "enforcement",
        }
        missing = required - set(policy.keys())
        if missing:
            errors.append(f"Policy missing keys: {missing}")
        else:
            print(f"PASS: export policy valid (version {policy.get('version')})")

        return len(errors) == 0, errors
    except Exception as e:
        return False, [f"Export policy validation error: {e}"]


def check_deny_globs() -> tuple[bool, list[str]]:
    """Verify no deny-glob files present on disk."""
    errors = []
    policy_path = Path("16_codex/opencore_export_policy.yaml")

    if not policy_path.exists():
        return False, [f"Export policy not found: {policy_path}"]

    try:
        with open(policy_path) as f:
            policy = yaml.safe_load(f)

        deny_globs = policy.get("deny_globs", [])
        violations = []

        for p in Path(".").rglob("*"):
            if not p.is_file() or ".git" in str(p):
                continue
            posix = p.as_posix()
            for pattern in deny_globs:
                import fnmatch

                if fnmatch.fnmatch(posix, pattern):
                    violations.append(f"{posix} matches deny pattern: {pattern}")
                    break

        if violations:
            for v in violations[:5]:  # Show first 5
                errors.append(f"DENY-GLOB VIOLATION: {v}")
        else:
            print("PASS: no deny-glob violations in repo")

        return len(violations) == 0, errors
    except Exception as e:
        return False, [f"Deny-glob check error: {e}"]


def check_secrets() -> tuple[bool, list[str]]:
    """Scan for leaked secrets."""
    errors = []
    policy_path = Path("16_codex/opencore_export_policy.yaml")

    if not policy_path.exists():
        return False, [f"Export policy not found: {policy_path}"]

    try:
        with open(policy_path) as f:
            policy = yaml.safe_load(f)

        secret_patterns = policy.get("secret_scan_regex", [])
        violations = []

        for p in Path(".").rglob("*"):
            if not p.is_file() or ".git" in str(p) or p.suffix in [".pyc", ".o"]:
                continue
            try:
                content = p.read_text(errors="ignore")
                for pattern in secret_patterns:
                    if re.search(pattern, content):
                        violations.append(f"{p}: matches secret pattern")
                        break
            except Exception:
                pass

        if violations:
            for v in violations[:5]:
                errors.append(f"SECRET VIOLATION: {v}")
        else:
            print("PASS: no secret patterns detected")

        return len(violations) == 0, errors
    except Exception as e:
        return False, [f"Secret scan error: {e}"]


def check_structure() -> tuple[bool, list[str]]:
    """Verify module directories have required files."""
    errors = []
    required_roots = ["03_core", "12_tooling", "16_codex", "23_compliance", "24_meta_orchestration"]

    for root in required_roots:
        root_path = Path(root)
        if not root_path.is_dir():
            errors.append(f"Required root missing: {root}")
            continue

        if not (root_path / "module.yaml").exists():
            errors.append(f"{root}: missing module.yaml")
        if not (root_path / "README.md").exists():
            errors.append(f"{root}: missing README.md")

    if not errors:
        print(f"PASS: all {len(required_roots)} exported roots have required files")

    return len(errors) == 0, errors


def main():
    """Run all verification gates."""
    checks = [
        ("Ruff Lint", check_ruff_lint),
        ("Ruff Format", check_ruff_format),
        ("Module YAML", check_module_yaml),
        ("Export Policy", check_export_policy),
        ("Deny Globs", check_deny_globs),
        ("Secret Scan", check_secrets),
        ("Structure", check_structure),
    ]

    print("=" * 70)
    print("SSID-open-core Local Verification (Zero-Cost, Local-Only)")
    print("=" * 70)
    print()

    all_pass = True
    for name, check_func in checks:
        print(f"[{name}]")
        try:
            passed, errors = check_func()
            if not passed:
                all_pass = False
                for error in errors:
                    print(f"  FAIL: {error}")
            print()
        except Exception as e:
            print(f"  ERROR: {e}")
            all_pass = False
            print()

    print("=" * 70)
    if all_pass:
        print("VERIFICATION PASS: All gates green ✅")
        print("=" * 70)
        return 0
    else:
        print("VERIFICATION FAIL: One or more gates failed ❌")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    sys.exit(main())
