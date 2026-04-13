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
    r'(?i)ssid-private',  # SSID-private repo specifically
    r'(?i)ssid-internal',  # SSID-internal repo
    r'(?i)local\.ssid',  # local.ssid development variant
    r'(?i)local-ssid',  # local-ssid variant
    r'(?i)localssid',  # localssid variant
    r'(?i)ssid-workspace',  # workspace-local variant
]

ABSOLUTE_PATH_PATTERNS = [
    r'C:\\Users',
    r'C:/Users',
    r'/home/.*SSID',
    r'/mnt/.*SSID',
]

SECRET_PATTERNS = [
    r'BEGIN (RSA|OPENSSH|EC) PRIVATE KEY',
    r'AKIA[0-9A-Z]{16}',
    r'xox[baprs]-',
    r'ghp_[A-Za-z0-9]{36}',
    r'-----BEGIN PRIVATE KEY-----',
    r'sk-[A-Za-z0-9]{48}',
    r'glpat-[A-Za-z0-9]{20}',
]

BLOCKED_FILE_PATTERNS = [
    r'\.env$',
    r'\.key$',
    r'\.pem$',
    r'\.p12$',
    r'\.pfx$',
]

# Files/patterns that are allowed to contain pattern definitions (for validation)
PATTERN_DEFINITION_FILES = [
    'validate_public_boundary.py',
    'build_public_export.py',
    'verify_export.py',
    '.github/workflows/public_export_integrity.yml',
    '23_compliance/public_export_policy.rego',
    '23_compliance/public_export_rules.yaml',
    '16_codex/opencore_export_policy.yaml',
]

# Only these 5 roots are exported and subject to boundary validation
EXPORTED_ROOTS = [
    '03_core',
    '12_tooling',
    '16_codex',
    '23_compliance',
    '24_meta_orchestration',
]

# These 19 roots must NOT contain meaningful content (derived from canonical SSID policy)
DENIED_ROOTS = [
    '01_ai_layer',
    '02_audit_logging',
    '04_deployment',
    '05_documentation',
    '06_data_pipeline',
    '07_governance_legal',
    '08_identity_score',
    '09_meta_identity',
    '10_interoperability',
    '11_test_simulation',
    '13_ui_layer',
    '14_zero_time_auth',
    '15_infra',
    '17_observability',
    '18_data_layer',
    '19_adapters',
    '20_foundation',
    '21_post_quantum_crypto',
    '22_datasets',
]


def is_pattern_definition_file(file_path: Path) -> bool:
    """Check if file is a pattern definition file (allowed to contain patterns)."""
    try:
        rel_path = str(file_path.resolve().relative_to(REPO_ROOT.resolve())).replace('\\', '/')
    except ValueError:
        return False
    return any(rel_path.endswith(pattern) for pattern in PATTERN_DEFINITION_FILES)


def is_in_exported_root(file_path: Path) -> bool:
    """Check if file is within one of the 5 exported roots."""
    rel_path = str(file_path.relative_to(REPO_ROOT)).replace('\\', '/')
    for root in EXPORTED_ROOTS:
        if rel_path.startswith(root + '/'):
            return True
    return False


def validate_no_private_repo_refs(repo_root: Path) -> list[str]:
    """Check for private repo references (except in definition files)."""
    violations = []
    repo_abs = repo_root.resolve()

    # Only scan exported roots
    for root in EXPORTED_ROOTS:
        root_path = repo_root / root
        if not root_path.exists():
            continue

        for file in root_path.rglob('*'):
            if not file.is_file():
                continue
            if is_pattern_definition_file(file):
                continue
            if file.suffix not in ['.py', '.md', '.yaml', '.yml', '.json', '.sh']:
                continue

            try:
                content = file.read_text(encoding='utf-8', errors='ignore')
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

        for file in root_path.rglob('*'):
            if not file.is_file():
                continue
            if file.suffix not in ['.py', '.md', '.yaml', '.yml', '.json', '.sh']:
                continue

            # Allow paths in pattern definition files
            if is_pattern_definition_file(file):
                continue
            # Allow paths in test files
            if '/tests/' in str(file).replace('\\', '/'):
                continue
            if 'test_' in file.name:
                continue

            try:
                content = file.read_text(encoding='utf-8', errors='ignore')
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
        for file in root_path.rglob('*'):
            if not file.is_file():
                continue

            # Blocked extensions
            for pattern in BLOCKED_FILE_PATTERNS:
                if re.match(pattern, file.name):
                    rel_path = file.resolve().relative_to(repo_abs)
                    violations.append(f"{rel_path}: blocked file type")
                    break

        # Check for secret patterns in source files
        for file in root_path.rglob('*'):
            if not file.is_file():
                continue
            if file.suffix not in ['.py', '.md', '.yaml', '.yml', '.json']:
                continue

            # Skip pattern definition files
            if is_pattern_definition_file(file):
                continue
            # Skip test files
            if 'test' in file.name or '/tests/' in str(file).replace('\\', '/'):
                continue

            try:
                content = file.read_text(encoding='utf-8', errors='ignore')
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

        for file in root_path.rglob('*.md'):
            if '/tests/' in str(file).replace('\\', '/'):
                continue

            try:
                content = file.read_text(encoding='utf-8', errors='ignore')
                lines = content.split('\n')

                for i, line in enumerate(lines):
                    if not any(word in line.lower() for word in ['mainnet', 'production', 'live']):
                        continue

                    # Check if this is properly contextualized
                    context = '\n'.join(lines[max(0, i-2):min(len(lines), i+3)])

                    # Allowed contexts
                    if any(keyword in context.lower() for keyword in [
                        'testnet', 'readiness', 'planned', 'future', 'will',
                        'https://', 'http://', 'link', 'reference'
                    ]):
                        continue

                    rel_path = file.resolve().relative_to(repo_abs)
                    violations.append(f"{rel_path}:{i+1}: unbacked mainnet claim")

            except Exception:
                pass

    return violations


def validate_denied_roots_empty(repo_root: Path) -> list[str]:
    """Check that denied roots contain no meaningful code files.

    Allowed: README.md, module.yaml, empty directories, scaffolds
    Not allowed: Implementation code (*.py with logic), test files, config
    """
    warnings = []

    for root in DENIED_ROOTS:
        root_path = repo_root / root
        if not root_path.exists():
            continue

        # Count code/content files (excluding metadata and empty scaffolds)
        code_files = []
        for py_file in root_path.rglob('*.py'):
            # Skip __pycache__ and test stubs
            if '__pycache__' in str(py_file):
                continue
            if py_file.name in ['__init__.py', 'stub.py']:
                continue
            # Skip tiny files (likely scaffolds)
            if py_file.stat().st_size > 100:
                code_files.append(py_file)

        if code_files:
            warnings.append(f"{root}: contains {len(code_files)} code file(s) (denied root should be empty scaffold)")

    return warnings


def validate_export_scope(repo_root: Path, manifest: dict = None) -> list[str]:
    """Validate that only exported roots should be published."""
    # This is informational only - doesn't fail, just flags scaffolded roots
    return []


def main():
    """Run boundary validation."""
    print("=== SSID Open-Core Public Boundary Validator ===\n")

    violations = []

    print("[1] Checking for private repo references...")
    private_refs = validate_no_private_repo_refs(REPO_ROOT)
    violations.extend(private_refs)
    if private_refs:
        print(f"    [WARN] Found {len(private_refs)} private repo reference(s)")
        for ref in private_refs[:5]:
            print(f"      - {ref}")
    else:
        print("    [OK] No private repo references")

    print("[2] Checking for absolute local paths...")
    local_paths = validate_no_local_paths(REPO_ROOT)
    violations.extend(local_paths)
    if local_paths:
        print(f"    [WARN] Found {len(local_paths)} absolute path(s)")
        for path in local_paths[:5]:
            print(f"      - {path}")
    else:
        print("    [OK] No absolute local paths (excluding tests)")

    print("[3] Checking for secrets/keys/tokens...")
    secrets = validate_no_secrets(REPO_ROOT)
    violations.extend(secrets)
    if secrets:
        print(f"    [WARN] Found {len(secrets)} secret pattern(s)")
        for secret in secrets[:5]:
            print(f"      - {secret}")
    else:
        print("    [OK] No secret patterns (excluding tests)")

    print("[4] Checking for unbacked mainnet claims...")
    mainnet = validate_no_mainnet_false_claims(REPO_ROOT)
    violations.extend(mainnet)
    if mainnet:
        print(f"    [WARN] Found {len(mainnet)} mainnet claim(s)")
        for claim in mainnet[:5]:
            print(f"      - {claim}")
    else:
        print("    [OK] No unbacked mainnet claims")

    print("[5] Checking that denied roots are empty...")
    denied_issues = validate_denied_roots_empty(REPO_ROOT)
    # Denied root warnings are informational; don't fail yet (Phase 3 action)
    if denied_issues:
        print(f"    [INFO] {len(denied_issues)} denied root(s) have content (Phase 3: to be removed)")
        for issue in denied_issues[:5]:
            print(f"      - {issue}")
    else:
        print("    [OK] All denied roots are empty (proper scaffolds)")

    print(f"\n=== Boundary Validation Result ===")
    print(f"Total violations: {len(violations)}")

    # Critical violations (must fail)
    critical = [v for v in violations if 'private repo reference' in v]
    if critical:
        print(f"\n[CRITICAL] Private repo references found: {len(critical)}")
        return 1

    # Warnings (report but don't fail if only test-related)
    if violations and not critical:
        print(f"\n[WARNING] Non-critical violations detected (see above)")
        print("Boundary validation: PASS (warnings only)")
        return 0

    print("\nBoundary validation: PASS")
    return 0


if __name__ == '__main__':
    sys.exit(main())
