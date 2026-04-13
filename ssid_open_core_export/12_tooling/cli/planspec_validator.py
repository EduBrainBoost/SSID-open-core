#!/usr/bin/env python3
"""
SSID PlanSpec Validator — validates multi-task plan specifications.

Checks:
  1. Required fields present (plan_id, title, tasks, acceptance_criteria)
  2. Each task has required fields (task_id, title)
  3. All depends_on references resolve to tasks within the plan
  4. No circular dependencies in task graph
  5. All task_ids are unique within the plan
  6. Optionally: referenced task_ids exist as TaskSpec files on disk

Exit codes: 0 = PASS, 1 = FAIL, 2 = ERROR
Output contract: PASS/FAIL + findings only. No scores.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TASK_SPEC_DIR = PROJECT_ROOT / "24_meta_orchestration" / "tasks" / "specs"

REQUIRED_TOP = ["plan_id", "title", "tasks", "acceptance_criteria"]
REQUIRED_TASK = ["task_id", "title"]


def load_planspec(path: Path) -> dict[str, Any]:
    """Load and parse a PlanSpec YAML file."""
    text = path.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError(f"PlanSpec must be a YAML mapping, got {type(data).__name__}")
    return data


def validate_structure(data: dict[str, Any]) -> list[str]:
    """Check required fields and structure. Returns list of findings."""
    findings: list[str] = []

    for field in REQUIRED_TOP:
        if field not in data:
            findings.append(f"Missing required top-level field: {field}")

    tasks = data.get("tasks", [])
    if not isinstance(tasks, list):
        findings.append(f"'tasks' must be a list, got {type(tasks).__name__}")
        return findings

    if len(tasks) == 0:
        findings.append("'tasks' must contain at least one task")

    ac = data.get("acceptance_criteria", [])
    if isinstance(ac, list) and len(ac) == 0:
        findings.append("'acceptance_criteria' must contain at least one criterion")

    task_ids: list[str] = []
    for i, task in enumerate(tasks):
        if not isinstance(task, dict):
            findings.append(f"Task {i} must be a mapping, got {type(task).__name__}")
            continue
        for field in REQUIRED_TASK:
            if field not in task:
                findings.append(f"Task {i} missing required field: {field}")
        tid = task.get("task_id", "")
        if tid:
            if tid in task_ids:
                findings.append(f"Duplicate task_id: {tid}")
            task_ids.append(tid)

    return findings


def validate_dependencies(data: dict[str, Any]) -> list[str]:
    """Check dependency references and cycle-freedom. Returns findings."""
    findings: list[str] = []
    tasks = data.get("tasks", [])
    if not isinstance(tasks, list):
        return findings

    task_ids = {t.get("task_id") for t in tasks if isinstance(t, dict) and t.get("task_id")}

    # Build adjacency: task -> depends_on
    graph: dict[str, list[str]] = {}
    for task in tasks:
        if not isinstance(task, dict):
            continue
        tid = task.get("task_id", "")
        deps = task.get("depends_on", [])
        if not isinstance(deps, list):
            findings.append(f"Task {tid}: 'depends_on' must be a list")
            deps = []
        for dep in deps:
            if dep not in task_ids:
                findings.append(f"Task {tid}: depends_on '{dep}' not found in plan tasks")
        graph[tid] = [d for d in deps if d in task_ids]

    # Cycle detection via DFS
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {tid: WHITE for tid in task_ids}

    def dfs(node: str) -> bool:
        color[node] = GRAY
        for neighbor in graph.get(node, []):
            if color.get(neighbor) == GRAY:
                findings.append(f"Circular dependency detected involving: {node} -> {neighbor}")
                return True
            if color.get(neighbor) == WHITE and dfs(neighbor):
                return True
        color[node] = BLACK
        return False

    for tid in task_ids:
        if color[tid] == WHITE:
            dfs(tid)

    return findings


def validate_taskspec_refs(data: dict[str, Any], spec_dir: Path) -> list[str]:
    """Check that referenced task_ids have corresponding TaskSpec files on disk."""
    findings: list[str] = []
    tasks = data.get("tasks", [])
    if not isinstance(tasks, list):
        return findings

    existing_specs = {p.stem for p in spec_dir.glob("*.yaml")} if spec_dir.exists() else set()

    for task in tasks:
        if not isinstance(task, dict):
            continue
        tid = task.get("task_id", "")
        if tid and tid not in existing_specs:
            findings.append(f"Task {tid}: no matching TaskSpec file in {spec_dir.relative_to(PROJECT_ROOT)}")

    return findings


def validate(path: Path, check_refs: bool = False) -> tuple[str, list[str]]:
    """Full validation. Returns (verdict, findings)."""
    data = load_planspec(path)
    findings: list[str] = []
    findings.extend(validate_structure(data))
    findings.extend(validate_dependencies(data))
    if check_refs:
        findings.extend(validate_taskspec_refs(data, TASK_SPEC_DIR))
    verdict = "PASS" if not findings else "FAIL"
    return verdict, findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a PlanSpec YAML file.")
    parser.add_argument("path", help="Path to the PlanSpec YAML file")
    parser.add_argument("--check-refs", action="store_true", help="Also check that task_ids exist as TaskSpec files")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    path = Path(args.path)
    if not path.exists():
        print(f"ERROR: File not found: {path}")
        return 2

    try:
        verdict, findings = validate(path, check_refs=args.check_refs)
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 2

    if args.json:
        result = {"verdict": verdict, "findings": findings}
        print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(f"PlanSpec Validation: {verdict}")
        for f in findings:
            print(f"  - {f}")

    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
