#!/usr/bin/env python3
"""
SSID CI Gates Parity Checker v4.1
Ensures local gates match CI gates exactly
"""
from __future__ import annotations

import argparse
import datetime
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple


class CIGatesParityChecker:
    """Verifies local gates match CI gates exactly"""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.ci_config = repo_root / ".github" / "workflows" / "gates.yml"
        self.local_gates_script = repo_root / "12_tooling" / "cli" / "run_all_gates.py"
        self.dispatcher = repo_root / "12_tooling" / "cli" / "ssid_dispatcher.py"

    def _run_command(self, cmd: List[str], cwd: Path = None) -> Tuple[int, str, str]:
        """Run command and return exit code, stdout, stderr"""
        proc = subprocess.run(
            cmd,
            cwd=cwd or self.repo_root,
            capture_output=True,
            text=True,
            encoding="utf-8"
        )
        return proc.returncode, proc.stdout, proc.stderr

    def _parse_ci_gates(self) -> List[Dict[str, Any]]:
        """Parse CI gates configuration from GitHub Actions workflow"""
        if not self.ci_config.exists():
            return []

        content = self.ci_config.read_text(encoding="utf-8")

        # Extract gate steps from workflow (simplified parsing)
        gates = []
        lines = content.splitlines()
        current_gate = None

        for line in lines:
            line = line.strip()
            if "Run Policy Gate" in line:
                current_gate = {"name": "policy", "type": "policy_gate"}
            elif "Run SoT Gate" in line:
                current_gate = {"name": "sot", "type": "sot_gate"}
            elif "Run QA Master Suite" in line:
                current_gate = {"name": "qa", "type": "qa_master_suite"}
            elif "Verify Dispatcher Gates" in line:
                current_gate = {"name": "dispatcher", "type": "dispatcher_gates"}
            elif current_gate and "run:" in line:
                # Extract command from next lines
                cmd_lines = []
                # Look ahead for command lines
                idx = lines.index(line) + 1
                while idx < len(lines) and (lines[idx].startswith("      ") or lines[idx].startswith("        ")):
                    cmd_line = lines[idx].strip()
                    if cmd_line and not cmd_line.startswith("#"):
                        cmd_lines.append(cmd_line)
                    idx += 1
                current_gate["command"] = " ".join(cmd_lines)
                gates.append(current_gate)
                current_gate = None

        return gates

    def _get_local_gates(self) -> List[Dict[str, Any]]:
        """Get local gates configuration"""
        gates = []

        # Policy gate
        policy_cmd = [sys.executable, str(self.local_gates_script), "--policy-only"]
        gates.append({
            "name": "policy",
            "type": "policy_gate",
            "command": " ".join(policy_cmd),
            "script": str(self.local_gates_script),
            "args": ["--policy-only"]
        })

        # SoT gate
        sot_cmd = [sys.executable, str(self.local_gates_script)]
        gates.append({
            "name": "sot",
            "type": "sot_gate",
            "command": " ".join(sot_cmd),
            "script": str(self.local_gates_script),
            "args": []
        })

        # QA Master Suite
        qa_cmd = [sys.executable, "02_audit_logging/archives/qa_master_suite/qa_master_suite.py", "--mode", "minimal"]
        gates.append({
            "name": "qa",
            "type": "qa_master_suite",
            "command": " ".join(qa_cmd),
            "script": "02_audit_logging/archives/qa_master_suite/qa_master_suite.py",
            "args": ["--mode", "minimal"]
        })

        # Dispatcher gates
        dispatcher_cmd = [sys.executable, str(self.dispatcher), "gates"]
        gates.append({
            "name": "dispatcher",
            "type": "dispatcher_gates",
            "command": " ".join(dispatcher_cmd),
            "script": str(self.dispatcher),
            "args": ["gates"]
        })

        return gates

    def _compare_gate_commands(self, ci_gate: Dict[str, Any], local_gate: Dict[str, Any]) -> List[str]:
        """Compare CI and local gate commands"""
        differences = []

        # Extract command components for comparison
        ci_cmd = ci_gate.get("command", "")
        local_cmd = local_gate.get("command", "")

        # Normalize commands (remove extra spaces, etc.)
        ci_normalized = " ".join(ci_cmd.split())
        local_normalized = " ".join(local_cmd.split())

        if ci_normalized != local_normalized:
            differences.append(f"Command mismatch:\\n  CI: {ci_cmd}\\n  Local: {local_cmd}")

        return differences

    def _run_gate_comparison(self, gate_name: str, ci_gate: Dict[str, Any], local_gate: Dict[str, Any]) -> Dict[str, Any]:
        """Run both CI and local gates and compare results"""
        result = {
            "gate_name": gate_name,
            "ci_exit_code": None,
            "local_exit_code": None,
            "ci_stdout": "",
            "local_stdout": "",
            "ci_stderr": "",
            "local_stderr": "",
            "exit_codes_match": False,
            "outputs_match": False,
            "differences": []
        }

        # Run CI gate command
        if ci_gate.get("command"):
            ci_cmd_parts = ci_gate["command"].split()
            result["ci_exit_code"], result["ci_stdout"], result["ci_stderr"] = self._run_command(ci_cmd_parts)

        # Run local gate command
        if local_gate.get("command"):
            local_cmd_parts = local_gate["command"].split()
            result["local_exit_code"], result["local_stdout"], result["local_stderr"] = self._run_command(local_cmd_parts)

        # Compare results
        if result["ci_exit_code"] is not None and result["local_exit_code"] is not None:
            result["exit_codes_match"] = result["ci_exit_code"] == result["local_exit_code"]
            if not result["exit_codes_match"]:
                result["differences"].append(f"Exit code mismatch: CI={result['ci_exit_code']}, Local={result['local_exit_code']}")

        # Compare outputs (normalize whitespace)
        ci_stdout_norm = " ".join(result["ci_stdout"].split()) if result["ci_stdout"] else ""
        local_stdout_norm = " ".join(result["local_stdout"].split()) if result["local_stdout"] else ""
        result["outputs_match"] = ci_stdout_norm == local_stdout_norm
        if not result["outputs_match"] and (ci_stdout_norm or local_stdout_norm):
            result["differences"].append("Output content differs")

        return result

    def check_parity(self, run_comparison: bool = False) -> Dict[str, Any]:
        """Check parity between CI and local gates"""
        ci_gates = self._parse_ci_gates()
        local_gates = self._get_local_gates()

        parity_report = {
            "check_timestamp": datetime.datetime.now(datetime.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "ci_gates_count": len(ci_gates),
            "local_gates_count": len(local_gates),
            "gates_match": len(ci_gates) == len(local_gates),
            "gate_results": {},
            "overall_parity": True,
            "recommendations": []
        }

        # Map gates by name for comparison
        ci_gates_map = {gate["name"]: gate for gate in ci_gates}
        local_gates_map = {gate["name"]: gate for gate in local_gates}

        # Check each gate
        all_gate_names = set(ci_gates_map.keys()) | set(local_gates_map.keys())

        for gate_name in sorted(all_gate_names):
            ci_gate = ci_gates_map.get(gate_name)
            local_gate = local_gates_map.get(gate_name)

            gate_result = {
                "gate_name": gate_name,
                "ci_exists": ci_gate is not None,
                "local_exists": local_gate is not None,
                "command_differences": [],
                "comparison_result": None
            }

            if ci_gate and local_gate:
                # Compare commands
                gate_result["command_differences"] = self._compare_gate_commands(ci_gate, local_gate)

                # Run comparison if requested
                if run_comparison:
                    gate_result["comparison_result"] = self._run_gate_comparison(gate_name, ci_gate, local_gate)

                    # Update overall parity based on comparison
                    if not gate_result["comparison_result"]["exit_codes_match"]:
                        parity_report["overall_parity"] = False
                        parity_report["recommendations"].append(f"Fix {gate_name} gate exit code mismatch")

                # Update overall parity based on command differences
                if gate_result["command_differences"]:
                    parity_report["overall_parity"] = False
                    parity_report["recommendations"].append(f"Align {gate_name} gate commands between CI and local")

            else:
                # Missing gate
                parity_report["overall_parity"] = False
                if not ci_gate:
                    parity_report["recommendations"].append(f"Add {gate_name} gate to CI configuration")
                if not local_gate:
                    parity_report["recommendations"].append(f"Add {gate_name} gate to local configuration")

            parity_report["gate_results"][gate_name] = gate_result

        return parity_report

    def fix_parity(self) -> List[str]:
        """Attempt to fix parity issues automatically"""
        fixes_applied = []

        # For now, just report what would need to be fixed
        # Real implementation would update CI config or local scripts
        parity_report = self.check_parity()

        if not parity_report["overall_parity"]:
            for recommendation in parity_report["recommendations"]:
                fixes_applied.append(f"TODO: {recommendation}")

        return fixes_applied

def main() -> int:
    parser = argparse.ArgumentParser(description="SSID CI Gates Parity Checker v4.1")
    parser.add_argument("--run-comparison", action="store_true",
                       help="Run actual gate commands to compare results")
    parser.add_argument("--fix", action="store_true",
                       help="Attempt to fix parity issues automatically")
    parser.add_argument("--repo-root", help="Repository root (default: auto-detect)")
    parser.add_argument("--output-json", help="Output parity report to JSON file")

    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve() if args.repo_root else Path(__file__).resolve().parents[2]
    checker = CIGatesParityChecker(repo_root)

    print("INFO: SSID CI Gates Parity Checker v4.1")
    print(f"INFO: Repository root: {repo_root}")

    # Check parity
    parity_report = checker.check_parity(run_comparison=args.run_comparison)

    # Display results
    print("\\n=== PARITY REPORT ===")
    print(f"CI Gates: {parity_report['ci_gates_count']}")
    print(f"Local Gates: {parity_report['local_gates_count']}")
    print(f"Gates Match: {parity_report['gates_match']}")
    print(f"Overall Parity: {parity_report['overall_parity']}")

    if not parity_report["overall_parity"]:
        print("\\n=== ISSUES FOUND ===")
        for gate_name, result in parity_report["gate_results"].items():
            if result["command_differences"]:
                print(f"\\n{gate_name.upper()} Gate:")
                for diff in result["command_differences"]:
                    print(f"  - {diff}")

            if result.get("comparison_result") and not result["comparison_result"]["exit_codes_match"]:
                print(f"\\n{gate_name.upper()} Gate:")
                print(f"  - Exit code mismatch: CI={result['comparison_result']['ci_exit_code']}, Local={result['comparison_result']['local_exit_code']}")

        print("\\n=== RECOMMENDATIONS ===")
        for rec in parity_report["recommendations"]:
            print(f"  - {rec}")
    else:
        print("\\nâœ… All gates are in parity!")

    # Save JSON report if requested
    if args.output_json:
        output_path = Path(args.output_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(parity_report, indent=2), encoding="utf-8")
        print(f"\\nINFO: Parity report saved to: {output_path}")

    # Attempt fixes if requested
    if args.fix:
        print("\\n=== ATTEMPTING FIXES ===")
        fixes = checker.fix_parity()
        if fixes:
            for fix in fixes:
                print(f"  - {fix}")
        else:
            print("  No automatic fixes available")

    return 0 if parity_report["overall_parity"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
