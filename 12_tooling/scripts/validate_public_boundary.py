#!/usr/bin/env python3
"""
SSID Open-Core Public Boundary Validator.

Enforces public-safety boundaries for SSID-open-core:
1. No private repo references as automatic ingest/export source
2. No absolute local paths
3. No secrets, keys, tokens, .env files
4. No unbacked mainnet/production claims
5. Export scope enforcement

Classification: Public (SSID-open-core only)
Version: 1.0.0
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Boundary rules
PRIVATE_REPO_PATTERNS = [
    r"(?i)ssid-private",  # SSID-private repo specifically
    r"(?i)ssid-internal",  # SSID-internal repo
    r"(?i)local\.ssid",  # local.ssid development variant
    r"(?i)local-ssid",  # local-ssid variant
    r"(?i)localssid",  # localssid variant
    r"(?i)ssid-workspace",  # workspace-local variant
]

ABSOLUTE_PATH_PATTERNS = [
    r"C:\\Users",
    r"C:/Users",
    r"/home/.*SSID",
    r"/mnt/.*SSID",
]

SECRET_PATTERNS = [
    r"BEGIN (RSA|OPENSSH|EC) PRIVATE KEY",
    r"AKIA[0-9A-Z]{16}",
    r"xox[baprs]-",
    r"ghp_[A-Za-z0-9]{36}",
    r"-----BEGIN PRIVATE KEY-----",
    r"sk-[A-Za-z0-9]{48}",
    r"glpat-[A-Za-z0-9]{20}",
]

BLOCKED_FILE_PATTERNS = [
    r"\.env$",
    r"\.key$",
    r"\.pem$",
    r"\.p12$",
    r"\.pfx$",
]

# Files/patterns that are allowed to contain pattern definitions (for validation)
PATTERN_DEFINITION_FILES = [
    "validate_public_boundary.py",
    "build_public_export.py",
    "verify_export.py",
    ".github/workflows/public_export_integrity.yml",
    "23_compliance/public_export_policy.rego",
    "23_compliance/public_export_rules.yaml",
    "16_codex/opencore_export_policy.yaml",
]

# Only these 5 roots are exported and subject to boundary validation
EXPORTED_ROOTS = [
    "03_core",
    "12_tooling",
    "16_codex",
    "23_compliance",
    "24_meta_orchestration",
]

# These 19 roots must NOT contain meaningful content (derived from canonical SSID policy)
DENIED_ROOTS = [
    "01_ai_layer",
    "02_audit_logging",
    "04_deployment",
    "05_documentation",
    "06_data_pipeline",
    "07_governance_legal",
    "08_identity_score",
    "09_meta_identity",
    "10_interoperability",
    "11_test_simulation",
    "13_ui_layer",
    "14_zero_time_auth",
    "15_infra",
    "17_observability",
    "18_data_layer",
    "19_adapters",
    "20_foundation",
    "21_post_quantum_crypto",
    "22_datasets",
]


def is_pattern_definition_file(file_path: Path) -> bool:
    """Check if file is a pattern definition file (allowed to contain patterns)."""
    try:
        rel_path = str(file_path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return False
    return any(rel_path.endswith(pattern) for pattern in PATTERN_DEFINITION_FILES)


def is_in_exported_root(file_path: Path) -> bool:
    """Check if file is within one of the 5 exported roots."""
    rel_path = str(file_path.relative_to(REPO_ROOT)).replace("\\", "/")
    return any(rel_path.startswith(root + "/") for root in EXPORTED_ROOTS)


def validate_no_private_repo_refs(repo_root: Path) -> list[str]:
    """Check for private repo references (except in definition files)."""
    violations = []
    repo_abs = repo_root.resolve()

    # Only scan exported roots
    for root in EXPORTED_ROOTS:
        root_path = repo_root / root
        if not root_path.exists():
            continue

        for file in root_path.rglob("*"):
            if not file.is_file():
                continue
            if is_pattern_definition_file(file):
                continue
            if file.suffix not in [".py", ".md", ".yaml", ".yml", ".json", ".sh"]:
                continue

            try:
                content = file.read_text(encoding="utf-8", errors="ignore")
                for pattern in PRIVATE_REPO_PATTERNS:
                    if re.search(pattern, content):
                        rel_path = file.resolve().relative_to(repo_abs)
                        violations.append(f"{rel_path}: private repo reference")
                        break
            except Exception:
                pass

    return violations


def validate_no_local_paths(repo_root: Path) -> list[str]:
    """Check for absolute local paths (except in definition/test files)."""
    violations = []
    repo_abs = repo_root.resolve()

    # Only scan exported roots
    for root in EXPORTED_ROOTS:
        root_path = repo_root / root
        if not root_path.exists():
            continue

        for file in root_path.rglob("*"):
            if not file.is_file():
                continue
            if file.suffix not in [".py", ".md", ".yaml", ".yml", ".json", ".sh"]:
                continue

            # Allow paths in pattern definition files
            if is_pattern_definition_file(file):
                continue
            # Allow paths in test files
            if "/tests/" in str(file).replace("\\", "/"):
                continue
            if "test_" in file.name:
                continue

            try:
                content = file.read_text(encoding="utf-8", errors="ignore")
                for pattern in ABSOLUTE_PATH_PATTERNS:
                    if re.search(pattern, content):
                        rel_path = file.resolve().relative_to(repo_abs)
                        violations.append(f"{rel_path}: absolute local path")
                        break
            except Exception:
                pass

    return violations


def validate_no_secrets(repo_root: Path) -> list[str]:
    """Check for secret patterns and blocked file types."""
    violations = []
    repo_abs = repo_root.resolve()

    # Only scan exported roots
    for root in EXPORTED_ROOTS:
        root_path = repo_root / root
        if not root_path.exists():
            continue

        # Check for blocked file extensions
        for file in root_path.rglob("*"):
            if not file.is_file():
                continue

            # Blocked extensions
            for pattern in BLOCKED_FILE_PATTERNS:
                if re.match(pattern, file.name):
                    rel_path = file.resolve().relative_to(repo_abs)
                    violations.append(f"{rel_path}: blocked file type")
                    break

        # Check for secret patterns in source files
        for file in root_path.rglob("*"):
            if not file.is_file():
                continue
            if file.suffix not in [".py", ".md", ".yaml", ".yml", ".json"]:
                continue

            # Skip pattern definition files
            if is_pattern_definition_file(file):
                continue
            # Skip test files
            if "test" in file.name or "/tests/" in str(file).replace("\\", "/"):
                continue

            try:
                content = file.read_text(encoding="utf-8", errors="ignore")
                for pattern in SECRET_PATTERNS:
                    if re.search(pattern, content):
                        rel_path = file.resolve().relative_to(repo_abs)
                        violations.append(f"{rel_path}: secret pattern detected")
                        break
            except Exception:
                pass

    return violations


def validate_no_mainnet_false_claims(repo_root: Path) -> list[str]:
    """Check for unbacked mainnet/production claims."""
    violations = []
    repo_abs = repo_root.resolve()

    # Only scan exported roots
    for root in EXPORTED_ROOTS:
        root_path = repo_root / root
        if not root_path.exists():
            continue

        for file in root_path.rglob("*.md"):
            if "/tests/" in str(file).replace("\\", "/"):
                continue

            try:
                content = file.read_text(encoding="utf-8", errors="ignore")
                lines = content.split("\n")

                for i, line in enumerate(lines):
                    if not any(word in line.lower() for word in ["mainnet", "production", "live"]):
                        continue

                    # Check if this is properly contextualized
                    context = "\n".join(lines[max(0, i - 2) : min(len(lines), i + 3)])

                    # Allowed contexts
                    if any(
                        keyword in context.lower()
                        for keyword in [
                            "testnet",
                            "readiness",
                            "planned",
                            "future",
                            "will",
                            "https://",
                            "http://",
                            "link",
                            "reference",
                        ]
                    ):
                        continue

                    rel_path = file.resolve().relative_to(repo_abs)
                    violations.append(f"{rel_path}:{i + 1}: unbacked mainnet claim")

            except Exception:
                pass

    return violations


def validate_denied_roots_empty(repo_root: Path) -> list[str]:
    """Check that denied roots contain no meaningful implementation code (FAIL-CLOSED).

    Allowed in denied roots: README.md only
    Not allowed: Any implementation code files (.py, .yaml, .yml, .json, .md except README, .txt, .sh)

    Scans all file types in denied roots per R5 hardening.
    Phase 2 allows scaffold structure (README.md); Phase 3 will remove all content.
    """
    violations = []
    repo_abs = repo_root.resolve()

    # File types to scan in denied roots (R5 enhancement: all types, not just .py)
    CHECKED_EXTENSIONS = {".py", ".yaml", ".yml", ".json", ".md", ".txt", ".sh"}

    for root in DENIED_ROOTS:
        root_path = repo_root / root
        if not root_path.exists():
            continue

        # Scan for implementation code violations across all file types
        for file in root_path.rglob("*"):
            if not file.is_file():
                continue

            # Only check specified file types
            if file.suffix not in CHECKED_EXTENSIONS:
                continue

            rel_path = str(file.resolve().relative_to(repo_abs)).replace("\\", "/")
            file_name = file.name

            # ALLOWED: README.md (scaffold indicator)
            if file_name == "README.md":
                continue

            # ALLOWED: Empty __init__.py or stub files only
            if file_name == "__init__.py":
                try:
                    content = file.read_text(encoding="utf-8", errors="ignore").strip()
                    # Allow only empty or import-only __init__.py files (<100 bytes)
                    if len(content) < 100 and (content == "" or ("import" in content and len(content.split("\n")) <= 3)):
                        continue
                except Exception:
                    pass
                # If __init__.py has substantial code, flag as violation
                violations.append(f"{rel_path}: implementation code in denied root (__init__.py)")
                continue

            # DISALLOWED: All other files
            # Provide specific message based on file type
            file_desc = "Python" if file.suffix == ".py" else \
                       "YAML" if file.suffix in {".yaml", ".yml"} else \
                       "JSON" if file.suffix == ".json" else \
                       "shell" if file.suffix == ".sh" else \
                       "text" if file.suffix == ".txt" else \
                       "markdown"

            violations.append(f"{rel_path}: {file_desc} file in denied root")

    return violations


def validate_export_scope(repo_root: Path, manifest: dict = None) -> list[str]:
    """Validate that only exported roots should be published."""
    # This is informational only - doesn't fail, just flags scaffolded roots
    return []


def validate_exported_roots_complete(repo_root: Path) -> dict:
    """Verify that exported roots have expected content structure.

    Returns dict with 'status' (OK|PARTIAL|MISSING) and 'details'.
    """
    expected_subdirs = {
        "03_core": ["validators", "sot"],
        "12_tooling": ["cli", "scripts"],
        "16_codex": ["decisions"],
        "23_compliance": ["policies"],
        "24_meta_orchestration": ["dispatcher"],
    }

    completeness = {}
    for root, subdirs in expected_subdirs.items():
        root_path = repo_root / root
        if not root_path.exists():
            completeness[root] = "MISSING"
            continue

        found_subdirs = [d for d in subdirs if (root_path / d).exists()]
        if len(found_subdirs) == len(subdirs):
            completeness[root] = "OK"
        elif found_subdirs:
            completeness[root] = "PARTIAL"
        else:
            completeness[root] = "MISSING"

    overall = "OK" if all(v == "OK" for v in completeness.values()) else "PARTIAL"
    return {"status": overall, "details": completeness}


def main():
    """Run boundary validation with FAIL-CLOSED enforcement."""
    import json

    print("=== SSID Open-Core Public Boundary Validator ===\n")

    violations = []
    report = {
        "status": "PASS",
        "denied_root_violations": [],
        "exported_root_completeness": {},
        "total_violations": 0,
    }

    print("[1] Checking for private repo references...")
    private_refs = validate_no_private_repo_refs(REPO_ROOT)
    violations.extend(private_refs)
    if private_refs:
        print(f"    [CRITICAL] Found {len(private_refs)} private repo reference(s)")
        for ref in private_refs[:5]:
            print(f"      - {ref}")
    else:
        print("    [OK] No private repo references")

    print("[2] Checking for absolute local paths...")
    local_paths = validate_no_local_paths(REPO_ROOT)
    violations.extend(local_paths)
    if local_paths:
        print(f"    [CRITICAL] Found {len(local_paths)} absolute path(s)")
        for path in local_paths[:5]:
            print(f"      - {path}")
    else:
        print("    [OK] No absolute local paths (excluding tests)")

    print("[3] Checking for secrets/keys/tokens...")
    secrets = validate_no_secrets(REPO_ROOT)
    violations.extend(secrets)
    if secrets:
        print(f"    [CRITICAL] Found {len(secrets)} secret pattern(s)")
        for secret in secrets[:5]:
            print(f"      - {secret}")
    else:
        print("    [OK] No secret patterns (excluding tests)")

    print("[4] Checking for unbacked mainnet claims...")
    mainnet = validate_no_mainnet_false_claims(REPO_ROOT)
    violations.extend(mainnet)
    if mainnet:
        print(f"    [CRITICAL] Found {len(mainnet)} mainnet claim(s)")
        for claim in mainnet[:5]:
            print(f"      - {claim}")
    else:
        print("    [OK] No unbacked mainnet claims")

    print("[5] Checking that denied roots are empty (FAIL-CLOSED)...")
    denied_issues = validate_denied_roots_empty(REPO_ROOT)
    if denied_issues:
        print(f"    [CRITICAL] Found {len(denied_issues)} denied root violation(s)")
        violations.extend(denied_issues)
        report["denied_root_violations"] = denied_issues[:10]
    else:
        print("    [OK] All denied roots are empty (proper scaffolds)")

    print("[6] Checking exported roots for completeness...")
    completeness = validate_exported_roots_complete(REPO_ROOT)
    print(f"    [INFO] Exported root status: {completeness['status']}")
    for root, status in completeness["details"].items():
        print(f"      - {root}: {status}")
    report["exported_root_completeness"] = completeness["details"]

    print("\n=== Boundary Validation Result ===")
    print(f"Total violations: {len(violations)}")

    # Build report
    report["total_violations"] = len(violations)

    if violations:
        report["status"] = "FAIL"
        print(f"\n[FAIL] {len(violations)} boundary violation(s) detected:")
        for v in violations[:10]:
            print(f"  - {v}")
        if len(violations) > 10:
            print(f"  ... and {len(violations) - 10} more")
        print("\nBoundary validation: FAIL (hard-fail, exit 1)")
        print(f"\nJSON report:\n{json.dumps(report, indent=2)}")
        return 1

    print("\nBoundary validation: PASS")
    print(f"\nJSON report:\n{json.dumps(report, indent=2)}")
    return 0


if __name__ == "__main__":
    # Support --verify-all flag (no-op, always full verification)
    if "--verify-all" in sys.argv:
        sys.argv.remove("--verify-all")
    sys.exit(main())
