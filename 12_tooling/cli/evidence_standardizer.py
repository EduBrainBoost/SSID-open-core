#!/usr/bin/env python3
"""
SSID Evidence Bundle Standardizer v4.1
Standardizes evidence bundle format across all tasks and agents
"""
from __future__ import annotations

import json
import hashlib
import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass, asdict
import re

@dataclass
class EvidenceBundle:
    """Standardized evidence bundle format v4.1"""
    # Required fields (no defaults)
    bundle_id: str
    generated_utc: str
    task_id: str
    task_spec_sha256: str
    agent_roles: List[str]
    patch_sha256: str
    patch_bytes: int
    changed_paths: List[str]
    gate_results: List[Dict[str, Any]]
    overall_gate_status: str
    evidence_artifacts: List[str]
    hash_manifest: Dict[str, Any]
    duplicate_guard_passed: bool
    write_gate_passed: bool
    sot_sync_required: bool
    sot_sync_passed: bool
    
    # Optional fields with defaults
    bundle_version: str = "4.1"
    security_context: str = "ROOT-24-LOCK"
    tool_used: Optional[str] = None
    execution_mode: str = "sandbox"
    log_mode: str = "MINIMAL"
    release_id: Optional[str] = None
    release_applied: bool = False
    release_backup_path: Optional[str] = None

class EvidenceStandardizer:
    """Standardizes evidence bundles across the SSID ecosystem"""
    
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.evidence_root = repo_root / "02_audit_logging" / "evidence"
    
    def _sha256_file(self, path: Path) -> str:
        """Calculate SHA256 of file"""
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    
    def _utc_ts(self) -> str:
        """UTC timestamp"""
        return datetime.datetime.now(datetime.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    
    def _parse_manifest(self, manifest_path: Path) -> Dict[str, Any]:
        """Parse existing manifest file"""
        if not manifest_path.exists():
            return {}
        
        try:
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}
    
    def _parse_gate_status(self, gate_status_path: Path) -> Tuple[str, List[Dict[str, Any]]]:
        """Parse gate status file"""
        if not gate_status_path.exists():
            return "FAIL", []
        
        try:
            data = json.loads(gate_status_path.read_text(encoding="utf-8"))
            return data.get("overall_status", "FAIL"), data.get("gates", [])
        except (json.JSONDecodeError, UnicodeDecodeError):
            return "FAIL", []
    
    def _parse_hash_manifest(self, hash_manifest_path: Path) -> Dict[str, Any]:
        """Parse hash manifest file"""
        if not hash_manifest_path.exists():
            return {"files": []}
        
        try:
            return json.loads(hash_manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {"files": []}
    
    def _detect_tool_from_paths(self, changed_paths: List[str]) -> Optional[str]:
        """Detect tool used from paths and patterns"""
        # Simple heuristics - could be enhanced
        if any("claude" in p.lower() for p in changed_paths):
            return "claude"
        elif any("codex" in p.lower() or "gpt" in p.lower() for p in changed_paths):
            return "codex"
        elif any("gemini" in p.lower() for p in changed_paths):
            return "gemini"
        elif any("opencode" in p.lower() for p in changed_paths):
            return "opencode"
        return None
    
    def _validate_duplicate_guard(self, repo_root: Path, changed_paths: List[str]) -> bool:
        """Check if duplicate guard would pass"""
        # This is a simplified check - the actual duplicate guard is more comprehensive
        try:
            import ast
            import re
            
            # Check for duplicates in key files
            key_files = [
                "16_codex/contracts/sot/sot_contract.yaml",
                "03_core/validators/sot/sot_validator_core.py",
                "23_compliance/policies/sot/sot_policy.rego",
                "12_tooling/cli/sot_validator.py",
                "11_test_simulation/tests_compliance/test_sot_validator.py"
            ]
            
            for key_file in key_files:
                file_path = repo_root / key_file
                if not file_path.exists():
                    continue
                
                content = file_path.read_text(encoding="utf-8")
                
                # YAML rule_id duplicates
                if key_file.endswith(".yaml"):
                    rule_ids = re.findall(r"\\brule_id\\s*:\\s*['\\\"]?([A-Za-z0-9_.:-]+)['\\\"]?", content)
                    if len(set(rule_ids)) != len(rule_ids):
                        return False
                
                # Python function duplicates
                elif key_file.endswith(".py"):
                    try:
                        tree = ast.parse(content)
                        funcs = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
                        if len(set(funcs)) != len(funcs):
                            return False
                    except SyntaxError:
                        pass
                
                # Rego rule duplicates
                elif key_file.endswith(".rego"):
                    rule_ids = re.findall(r"\\brule_id\\s*[:=]\\s*['\\\"]([A-Za-z0-9_.:-]+)['\\\"]", content)
                    if len(set(rule_ids)) != len(rule_ids):
                        return False
            
            return True
        except Exception:
            return False
    
    def _check_sot_sync_required(self, changed_paths: List[str]) -> bool:
        """Check if SoT synchronization is required"""
        sot_files = [
            "03_core/validators/sot/sot_validator_core.py",
            "23_compliance/policies/sot/sot_policy.rego",
            "16_codex/contracts/sot/sot_contract.yaml",
            "12_tooling/cli/sot_validator.py",
            "11_test_simulation/tests_compliance/test_sot_validator.py",
            "02_audit_logging/reports/SOT_MOSCOW_ENFORCEMENT_V3.2.0.md"
        ]
        
        return any(path in changed_paths for path in sot_files)
    
    def _check_sot_sync_passed(self, repo_root: Path) -> bool:
        """Check if SoT synchronization is consistent"""
        sot_files = [
            "03_core/validators/sot/sot_validator_core.py",
            "23_compliance/policies/sot/sot_policy.rego", 
            "16_codex/contracts/sot/sot_contract.yaml",
            "12_tooling/cli/sot_validator.py",
            "11_test_simulation/tests_compliance/test_sot_validator.py",
            "02_audit_logging/reports/SOT_MOSCOW_ENFORCEMENT_V3.2.0.md"
        ]
        
        # For now, just check if all files exist
        # Real implementation would check consistency between them
        for sot_file in sot_files:
            if not (repo_root / sot_file).exists():
                return False
        
        return True
    
    def standardize_bundle(self, evidence_dir: Path) -> EvidenceBundle:
        """Standardize an evidence bundle"""
        # Extract basic information
        manifest_path = evidence_dir / "manifest.json"
        gate_status_path = evidence_dir / "gate_status.json"
        hash_manifest_path = evidence_dir / "hash_manifest.json"
        patch_path = evidence_dir / "patch.diff"
        
        # Parse existing files
        manifest = self._parse_manifest(manifest_path)
        overall_status, gate_results = self._parse_gate_status(gate_status_path)
        hash_manifest = self._parse_hash_manifest(hash_manifest_path)
        
        # Generate bundle ID
        timestamp = self._utc_ts().replace(":", "").replace("-", "")
        task_id = manifest.get("task_id", "unknown")
        bundle_id = f"{task_id}_{timestamp}"
        
        # Detect tool
        changed_paths = manifest.get("changed_paths", [])
        tool_used = manifest.get("tool") or self._detect_tool_from_paths(changed_paths)
        
        # Get patch information
        patch_sha256 = self._sha256_file(patch_path) if patch_path.exists() else ""
        patch_bytes = patch_path.stat().st_size if patch_path.exists() else 0
        
        # Check compliance
        duplicate_guard_passed = self._validate_duplicate_guard(self.repo_root, changed_paths)
        write_gate_passed = overall_status == "PASS"  # Simplified check
        sot_sync_required = self._check_sot_sync_required(changed_paths)
        sot_sync_passed = self._check_sot_sync_passed(self.repo_root) if sot_sync_required else True
        
        # Build standardized bundle
        bundle = EvidenceBundle(
            bundle_id=bundle_id,
            generated_utc=self._utc_ts(),
            task_id=task_id,
            task_spec_sha256=manifest.get("task_spec_sha256", ""),
            agent_roles=manifest.get("agent_roles", []),
            tool_used=tool_used,
            execution_mode=manifest.get("execution_mode", "sandbox"),
            log_mode=manifest.get("log_mode", "MINIMAL"),
            patch_sha256=patch_sha256,
            patch_bytes=patch_bytes,
            changed_paths=changed_paths,
            gate_results=gate_results,
            overall_gate_status=overall_status,
            evidence_artifacts=manifest.get("artifacts", []),
            hash_manifest=hash_manifest,
            duplicate_guard_passed=duplicate_guard_passed,
            write_gate_passed=write_gate_passed,
            sot_sync_required=sot_sync_required,
            sot_sync_passed=sot_sync_passed
        )
        
        return bundle
    
    def write_standardized_bundle(self, bundle: EvidenceBundle, output_dir: Path) -> Path:
        """Write standardized evidence bundle to directory"""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Write main bundle manifest
        bundle_manifest = output_dir / "evidence_bundle.json"
        bundle_manifest.write_text(
            json.dumps(asdict(bundle), indent=2, sort_keys=True), encoding="utf-8"
        )
        
        # Write verification summary
        verification = {
            "bundle_id": bundle.bundle_id,
            "verification_utc": self._utc_ts(),
            "compliance_status": {
                "duplicate_guard": "PASS" if bundle.duplicate_guard_passed else "FAIL",
                "write_gate": "PASS" if bundle.write_gate_passed else "FAIL", 
                "sot_sync": "PASS" if bundle.sot_sync_passed else "FAIL",
                "overall": "PASS" if all([
                    bundle.duplicate_guard_passed,
                    bundle.write_gate_passed,
                    bundle.sot_sync_passed
                ]) else "FAIL"
            },
            "gate_summary": {
                "total_gates": len(bundle.gate_results),
                "passed_gates": len([g for g in bundle.gate_results if g.get("status") == "PASS"]),
                "failed_gates": len([g for g in bundle.gate_results if g.get("status") == "FAIL"]),
                "overall_status": bundle.overall_gate_status
            }
        }
        
        verification_file = output_dir / "verification_summary.json"
        verification_file.write_text(
            json.dumps(verification, indent=2, sort_keys=True), encoding="utf-8"
        )
        
        return bundle_manifest

def main() -> int:
    import argparse
    
    parser = argparse.ArgumentParser(description="SSID Evidence Bundle Standardizer v4.1")
    parser.add_argument("evidence_dir", help="Path to evidence directory to standardize")
    parser.add_argument("--output-dir", help="Output directory for standardized bundle")
    parser.add_argument("--repo-root", help="Repository root (default: auto-detect)")
    
    args = parser.parse_args()
    
    evidence_dir = Path(args.evidence_dir).resolve()
    if not evidence_dir.exists():
        print(f"ERROR: Evidence directory not found: {evidence_dir}")
        return 1
    
    repo_root = Path(args.repo_root).resolve() if args.repo_root else Path(__file__).resolve().parents[2]
    output_dir = Path(args.output_dir).resolve() if args.output_dir else evidence_dir.parent / f"standardized_{evidence_dir.name}"
    
    standardizer = EvidenceStandardizer(repo_root)
    
    try:
        bundle = standardizer.standardize_bundle(evidence_dir)
        bundle_path = standardizer.write_standardized_bundle(bundle, output_dir)
        
        print(f"SUCCESS: Standardized bundle written to: {bundle_path}")
        print(f"BUNDLE_ID: {bundle.bundle_id}")
        print(f"COMPLIANCE_STATUS: {bundle.duplicate_guard_passed and bundle.write_gate_passed and bundle.sot_sync_passed}")
        
        return 0
        
    except Exception as e:
        print(f"ERROR: Standardization failed: {e}")
        return 1

if __name__ == "__main__":
    raise SystemExit(main())