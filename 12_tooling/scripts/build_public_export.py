#!/usr/bin/env python3
"""
SSID Open-Core Deterministic Public Export Builder.

Builds a deterministic, auditable public export manifest and evidence package.
Enforces public-safety boundaries and generates SHA256 evidence artifacts.

Classification: Public (SSID-open-core only)
Version: 1.0.0
"""

import json
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]


def load_yaml(path: Path) -> dict:
    """Load YAML safely."""
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


def compute_file_hash(path: Path, algorithm: str = 'sha256') -> str:
    """Compute file hash."""
    hasher = hashlib.new(algorithm)
    try:
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                hasher.update(chunk)
        return hasher.hexdigest()
    except (OSError, IOError):
        return None


def load_export_policy() -> dict:
    """Load export policy from canonical location."""
    path = REPO_ROOT / '16_codex' / 'opencore_export_policy.yaml'
    return load_yaml(path)


def load_current_manifest() -> dict:
    """Load current public export manifest."""
    path = REPO_ROOT / '16_codex' / 'public_export_manifest.json'
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def validate_no_private_refs(root_path: Path, policy: dict) -> list[str]:
    """Check for private repo references."""
    violations = []
    private_patterns = [
        'SSID-private',
        'ssid-private',
        'local.ssid',
        'local-ssid',
        'localSsid',
        '/mnt/ssid',
        'C:\\Users',
        'C:/Users',
    ]

    for file in root_path.rglob('*'):
        if file.is_file() and file.suffix in ['.py', '.md', '.yaml', '.yml', '.json']:
            try:
                content = file.read_text(encoding='utf-8', errors='ignore')
                for pattern in private_patterns:
                    if pattern.lower() in content.lower():
                        violations.append(f"{file.relative_to(REPO_ROOT)}: contains '{pattern}'")
            except Exception:
                pass

    return violations


def validate_no_local_paths(root_path: Path, policy: dict) -> list[str]:
    """Check for absolute local paths."""
    violations = []
    for file in root_path.rglob('*'):
        if file.is_file() and file.suffix in ['.py', '.md', '.yaml', '.yml', '.json']:
            try:
                content = file.read_text(encoding='utf-8', errors='ignore')
                if 'C:\\Users' in content or 'C:/Users' in content:
                    violations.append(f"{file.relative_to(REPO_ROOT)}: contains absolute path")
                if '/home/' in content and 'SSID' in content:
                    violations.append(f"{file.relative_to(REPO_ROOT)}: contains absolute path")
            except Exception:
                pass

    return violations


def validate_no_secrets(root_path: Path, policy: dict) -> list[str]:
    """Check for secret patterns."""
    violations = []
    secret_patterns = policy.get('secret_scan_regex', [])

    for file in root_path.rglob('*'):
        if file.is_file() and file.suffix in ['.env', '.key', '.pem', '.p12', '.pfx']:
            violations.append(f"{file.relative_to(REPO_ROOT)}: blocked file type")

        if file.is_file() and file.suffix in ['.py', '.yaml', '.yml', '.json', '.md']:
            try:
                content = file.read_text(encoding='utf-8', errors='ignore')
                if '.env' in content or 'PRIVATE KEY' in content or 'ghp_' in content:
                    violations.append(f"{file.relative_to(REPO_ROOT)}: potential secret detected")
            except Exception:
                pass

    return violations


def validate_no_mainnet_false_claims(root_path: Path) -> list[str]:
    """Check for unbacked mainnet/live/production claims."""
    violations = []

    for file in root_path.rglob('*.md'):
        try:
            content = file.read_text(encoding='utf-8', errors='ignore')
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if 'mainnet' in line.lower() or 'production' in line.lower():
                    # Check if this line has proper context/evidence reference
                    context = '\n'.join(lines[max(0, i-2):min(len(lines), i+3)])
                    if 'testnet' not in context.lower() and 'readiness' not in context.lower():
                        if 'https://' not in context and 'http://' not in context:
                            violations.append(
                                f"{file.relative_to(REPO_ROOT)}:{i+1}: unbacked mainnet claim"
                            )
        except Exception:
            pass

    return violations


def build_export_evidence() -> dict:
    """Build complete export evidence."""
    policy = load_export_policy()
    current_manifest = load_current_manifest()
    now_utc = datetime.now(timezone.utc).isoformat() + 'Z'

    evidence = {
        "export_id": f"export-{now_utc.split('T')[0]}-{hashlib.sha256(now_utc.encode()).hexdigest()[:8]}",
        "timestamp_utc": now_utc,
        "source_repo": "SSID",
        "target_repo": "SSID-open-core",
        "policy_version": policy.get('schema_version', '2.0.0'),
        "exported_roots": [],
        "validation_results": {
            "private_references": [],
            "local_paths": [],
            "secrets": [],
            "mainnet_claims": [],
        },
        "summary": {
            "total_roots": 0,
            "exported_count": 0,
            "scaffolded_count": 0,
            "violations": 0,
            "status": "PENDING",
        }
    }

    # Validate each root
    for root_info in current_manifest.get('exported_roots', []):
        root_name = root_info['root']
        root_path = REPO_ROOT / root_name

        if not root_path.exists():
            continue

        evidence['summary']['total_roots'] += 1

        # Run validators
        private_refs = validate_no_private_refs(root_path, policy)
        local_paths = validate_no_local_paths(root_path, policy)
        secrets = validate_no_secrets(root_path, policy)
        mainnet_claims = validate_no_mainnet_false_claims(root_path)

        evidence['validation_results']['private_references'].extend(private_refs)
        evidence['validation_results']['local_paths'].extend(local_paths)
        evidence['validation_results']['secrets'].extend(secrets)
        evidence['validation_results']['mainnet_claims'].extend(mainnet_claims)

        status = root_info.get('status', 'unknown')
        if status == 'exported':
            evidence['summary']['exported_count'] += 1
        else:
            evidence['summary']['scaffolded_count'] += 1

        # Add to evidence output
        root_evidence = {
            "root": root_name,
            "status": status,
            "description": root_info.get('description', ''),
            "public_safe": len(private_refs) == 0 and len(secrets) == 0,
            "violations_count": len(private_refs) + len(local_paths) + len(secrets),
        }
        evidence['exported_roots'].append(root_evidence)

    # Calculate violation count
    evidence['summary']['violations'] = (
        len(evidence['validation_results']['private_references']) +
        len(evidence['validation_results']['local_paths']) +
        len(evidence['validation_results']['secrets']) +
        len(evidence['validation_results']['mainnet_claims'])
    )

    # Final status
    evidence['summary']['status'] = 'PASS' if evidence['summary']['violations'] == 0 else 'FAIL'

    return evidence


def save_evidence(evidence: dict) -> Path:
    """Save evidence to evidence directory."""
    evidence_dir = REPO_ROOT / '23_compliance' / 'evidence' / 'public_export'
    evidence_dir.mkdir(parents=True, exist_ok=True)

    export_id = evidence['export_id']
    evidence_path = evidence_dir / f"{export_id}.json"

    with open(evidence_path, 'w', encoding='utf-8') as f:
        json.dump(evidence, f, indent=2)

    return evidence_path


def compute_manifest_hash(manifest: dict) -> str:
    """Compute hash of manifest."""
    manifest_str = json.dumps(manifest, sort_keys=True)
    return hashlib.sha256(manifest_str.encode()).hexdigest()


def main():
    """Build public export."""
    print("=== SSID Open-Core Public Export Builder ===\n")

    try:
        print("[1] Loading export policy...")
        policy = load_export_policy()
        print(f"    [OK] Policy version {policy.get('schema_version', 'unknown')}")

        print("[2] Loading current manifest...")
        manifest = load_current_manifest()
        print(f"    [OK] Manifest schema {manifest.get('schema', 'unknown')}")

        print("[3] Building export evidence...")
        evidence = build_export_evidence()
        print(f"    [OK] Export ID: {evidence['export_id']}")
        print(f"    [OK] Total roots: {evidence['summary']['total_roots']}")
        print(f"    [OK] Exported: {evidence['summary']['exported_count']}")
        print(f"    [OK] Scaffolded: {evidence['summary']['scaffolded_count']}")
        print(f"    [OK] Violations: {evidence['summary']['violations']}")

        print("[4] Validating boundaries...")
        if evidence['validation_results']['private_references']:
            print(f"    [WARN] Private references: {len(evidence['validation_results']['private_references'])}")
            for ref in evidence['validation_results']['private_references'][:3]:
                print(f"      - {ref}")

        if evidence['validation_results']['secrets']:
            print(f"    [WARN] Secret patterns: {len(evidence['validation_results']['secrets'])}")
            for secret in evidence['validation_results']['secrets'][:3]:
                print(f"      - {secret}")

        if evidence['validation_results']['local_paths']:
            print(f"    [WARN] Local paths: {len(evidence['validation_results']['local_paths'])}")

        if evidence['validation_results']['mainnet_claims']:
            print(f"    [WARN] Mainnet claims: {len(evidence['validation_results']['mainnet_claims'])}")

        print("[5] Computing checksums...")
        manifest_hash = compute_manifest_hash(manifest)
        print(f"    [OK] Manifest SHA256: {manifest_hash}")

        print("[6] Saving evidence...")
        evidence_path = save_evidence(evidence)
        print(f"    [OK] Evidence: {evidence_path.relative_to(REPO_ROOT)}")

        print(f"\n=== Export Status: {evidence['summary']['status']} ===")

        if evidence['summary']['status'] == 'FAIL':
            print(f"Violations: {evidence['summary']['violations']}")
            return 1

        print("Public export validated successfully.")
        return 0

    except Exception as e:
        print(f"\n[ERROR] {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
