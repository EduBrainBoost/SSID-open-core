#!/usr/bin/env python3
"""
SSID Parallel Execution Framework v4.1
H1: Parallel execution framework for deterministic multi-agent workflows
1 Task = 1 Sandbox Worktree, max 1Ã— Planner + 1Ã— Implementer + 1Ã— Auditor + 1Ã— Test Runner
"""

from __future__ import annotations

import argparse
import datetime
import json
import multiprocessing
import signal
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# SSID Configuration
REPO_ROOT = Path(__file__).resolve().parents[2]
DISPATCHER = REPO_ROOT / "12_tooling" / "cli" / "ssid_dispatcher.py"
MAX_CONCURRENT_TASKS = 4  # Configurable limit
TASK_TIMEOUT = 1800  # 30 minutes per task


@dataclass
class ParallelTask:
    """Individual task in parallel execution"""

    task_id: str
    task_spec_path: Path
    agent_roles: list[str]
    tool: str
    dependencies: list[str]
    priority: int = 5  # 1-10, lower is higher priority
    created_utc: str = ""

    def __post_init__(self):
        if not self.created_utc:
            self.created_utc = (
                datetime.datetime.now(datetime.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
            )


@dataclass
class TaskResult:
    """Result of completed parallel task"""

    task_id: str
    success: bool
    exit_code: int
    evidence_dir: Path | None
    error_message: str | None
    started_utc: str
    completed_utc: str
    execution_time_seconds: float


class ParallelExecutor:
    """Manages parallel execution of multiple SSID tasks"""

    def __init__(self, repo_root: Path | None = None, max_workers: int | None = None):
        self.repo_root = repo_root or REPO_ROOT
        self.dispatcher = DISPATCHER
        self.max_workers = max_workers or min(MAX_CONCURRENT_TASKS, multiprocessing.cpu_count())
        self.active_tasks: dict[str, subprocess.Popen | None] = {}
        self.task_queue: list[ParallelTask] = []
        self.completed_tasks: dict[str, TaskResult] = {}
        self.running = True

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print(f"\\nINFO: Received signal {signum}, initiating graceful shutdown...")
        self.running = False
        for task_id, proc in self.active_tasks.items():
            print(f"INFO: Terminating task {task_id}")
            if proc:
                proc.terminate()

    def _validate_task_spec(self, task_spec_path: Path) -> dict[str, Any]:
        """Validate task specification"""
        if not task_spec_path.exists():
            raise ValueError(f"Task spec not found: {task_spec_path}")

        try:
            if task_spec_path.suffix.lower() in [".yml", ".yaml"]:
                import yaml

                data = yaml.safe_load(task_spec_path.read_text(encoding="utf-8"))
            else:
                data = json.loads(task_spec_path.read_text(encoding="utf-8"))

            # Validate required fields
            required = ["task_id", "allowed_paths", "agent_roles", "patch_strategy", "log_mode", "prompt"]
            for field in required:
                if field not in data:
                    raise ValueError(f"Missing required field: {field}")

            return data

        except Exception as e:
            raise ValueError(f"Invalid task spec: {e}") from e

    def _create_task_spec_with_role(self, base_spec: dict[str, Any], role: str, tool: str) -> Path:
        """Create temporary task spec for specific role"""
        temp_spec = Path(tempfile.mktemp(suffix=".json"))

        role_spec = base_spec.copy()
        role_spec.update(
            {
                "task_id": f"{base_spec['task_id']}_{role.lower()}",
                "agent_roles": [role],
                "scope": role_spec.get("scope", {}),
                "expected_artifacts": role_spec.get("expected_artifacts", []),
                "acceptance_checks": role_spec.get("acceptance_checks", []),
                "tool_override": tool,
            }
        )

        # Role-specific modifications
        if role == "Planner":
            role_spec["allowed_paths"] = []  # Planners don't write files
        elif role == "ComplianceAuditor":
            role_spec["allowed_paths"] = []  # Auditors don't write files
        elif role == "TestRunner":
            role_spec["allowed_paths"] = []  # Test runners don't write files

        temp_spec.write_text(json.dumps(role_spec, indent=2), encoding="utf-8")
        return temp_spec

    def _execute_task(self, task: ParallelTask) -> TaskResult:
        """Execute a single task"""
        started_utc = datetime.datetime.now(datetime.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        start_time = time.time()

        try:
            print(f"INFO: Starting task {task.task_id} with {task.tool} for roles: {task.agent_roles}")

            # For now, execute first role only (can be enhanced for multiple roles)
            if not task.agent_roles:
                raise ValueError("No agent roles specified")

            role = task.agent_roles[0]
            temp_spec = self._create_task_spec_with_role(self._validate_task_spec(task.task_spec_path), role, task.tool)

            try:
                # Execute dispatcher run
                run_cmd = [sys.executable, str(self.dispatcher), "run", "--tool", task.tool, "--task", str(temp_spec)]
                run_proc = subprocess.run(
                    run_cmd,
                    cwd=str(self.repo_root),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=TASK_TIMEOUT,
                )

                if run_proc.returncode != 0:
                    return TaskResult(
                        task_id=task.task_id,
                        success=False,
                        exit_code=run_proc.returncode,
                        evidence_dir=None,
                        error_message=f"Run phase failed: {run_proc.stderr.strip()}",
                        started_utc=started_utc,
                        completed_utc=datetime.datetime.now(datetime.UTC)
                        .replace(microsecond=0)
                        .isoformat()
                        .replace("+00:00", "Z"),
                        execution_time_seconds=time.time() - start_time,
                    )

                # Extract sandbox directory
                sandbox_line = [line for line in run_proc.stdout.splitlines() if "SANDBOX:" in line]
                if not sandbox_line:
                    return TaskResult(
                        task_id=task.task_id,
                        success=False,
                        exit_code=1,
                        evidence_dir=None,
                        error_message="Could not extract sandbox directory from dispatcher output",
                        started_utc=started_utc,
                        completed_utc=datetime.datetime.now(datetime.UTC)
                        .replace(microsecond=0)
                        .isoformat()
                        .replace("+00:00", "Z"),
                        execution_time_seconds=time.time() - start_time,
                    )

                sandbox_dir = sandbox_line[0].split("SANDBOX:")[1].strip()

                # Execute the tool in the sandbox worktree
                tool_cmd = self._build_tool_command(task.tool, temp_spec, sandbox_dir)
                if tool_cmd:
                    tool_proc = subprocess.run(
                        tool_cmd,
                        cwd=sandbox_dir,
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        timeout=TASK_TIMEOUT,
                    )
                    if tool_proc.returncode != 0:
                        return TaskResult(
                            task_id=task.task_id,
                            success=False,
                            exit_code=tool_proc.returncode,
                            evidence_dir=None,
                            error_message=f"Tool execution failed: {tool_proc.stderr.strip()[:500]}",
                            started_utc=started_utc,
                            completed_utc=datetime.datetime.now(datetime.UTC)
                            .replace(microsecond=0)
                            .isoformat()
                            .replace("+00:00", "Z"),
                            execution_time_seconds=time.time() - start_time,
                        )

                # Package results
                package_cmd = [
                    sys.executable,
                    str(self.dispatcher),
                    "package",
                    "--task",
                    str(temp_spec),
                    "--sandbox",
                    sandbox_dir,
                ]
                package_proc = subprocess.run(
                    package_cmd,
                    cwd=str(self.repo_root),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=TASK_TIMEOUT,
                )

                completed_utc = (
                    datetime.datetime.now(datetime.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
                )

                if package_proc.returncode == 0:
                    # Extract evidence directory
                    evidence_line = [line for line in package_proc.stdout.splitlines() if "PACKAGE_SUCCESS:" in line]
                    if evidence_line:
                        evidence_dir = Path(evidence_line[0].split("PACKAGE_SUCCESS:")[1].strip())
                    else:
                        evidence_dir = None

                    return TaskResult(
                        task_id=task.task_id,
                        success=True,
                        exit_code=0,
                        evidence_dir=evidence_dir,
                        error_message=None,
                        started_utc=started_utc,
                        completed_utc=completed_utc,
                        execution_time_seconds=time.time() - start_time,
                    )
                else:
                    return TaskResult(
                        task_id=task.task_id,
                        success=False,
                        exit_code=package_proc.returncode,
                        evidence_dir=None,
                        error_message=f"Package phase failed: {package_proc.stderr.strip()}",
                        started_utc=started_utc,
                        completed_utc=completed_utc,
                        execution_time_seconds=time.time() - start_time,
                    )

            finally:
                # Cleanup temporary spec
                if temp_spec.exists():
                    temp_spec.unlink()

        except subprocess.TimeoutExpired:
            return TaskResult(
                task_id=task.task_id,
                success=False,
                exit_code=124,  # timeout exit code
                evidence_dir=None,
                error_message=f"Task timed out after {TASK_TIMEOUT} seconds",
                started_utc=started_utc,
                completed_utc=datetime.datetime.now(datetime.UTC)
                .replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z"),
                execution_time_seconds=time.time() - start_time,
            )

        except Exception as e:
            return TaskResult(
                task_id=task.task_id,
                success=False,
                exit_code=1,
                evidence_dir=None,
                error_message=f"Unexpected error: {str(e)}",
                started_utc=started_utc,
                completed_utc=datetime.datetime.now(datetime.UTC)
                .replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z"),
                execution_time_seconds=time.time() - start_time,
            )

    @staticmethod
    def _build_tool_command(tool: str, task_spec: Path, sandbox_dir: str) -> list[str]:
        """Build the CLI command to execute the given tool inside the sandbox.

        Maps each supported tool name to its actual CLI invocation. Returns an
        empty list if the tool is not locally executable (e.g. cloud-only tools).
        """
        tool_map: dict[str, list[str]] = {
            "claude": ["claude", "--task", str(task_spec)],
            "codex": ["codex", "--task", str(task_spec)],
            "gemini": ["gemini", "--task", str(task_spec)],
            "kilo": ["kilo", "run", "--task", str(task_spec)],
            "copilot": ["copilot", "run", "--task", str(task_spec)],
            "opencode": ["opencode", "run", "--task", str(task_spec)],
        }
        return tool_map.get(tool, [])

    def _check_dependencies(self, task: ParallelTask) -> bool:
        """Check if task dependencies are satisfied"""
        for dep_id in task.dependencies:
            if dep_id not in self.completed_tasks:
                return False
            if not self.completed_tasks[dep_id].success:
                return False
        return True

    def _get_ready_tasks(self) -> list[ParallelTask]:
        """Get tasks ready for execution"""
        ready_tasks = []
        for task in self.task_queue:
            if (
                self._check_dependencies(task)
                and task.task_id not in self.active_tasks
                and task.task_id not in self.completed_tasks
            ):
                ready_tasks.append(task)

        # Sort by priority (lower number = higher priority)
        ready_tasks.sort(key=lambda t: t.priority)
        return ready_tasks

    def execute_parallel(self, tasks: list[ParallelTask]) -> dict[str, TaskResult]:
        """Execute multiple tasks in parallel"""
        print(f"INFO: Starting parallel execution of {len(tasks)} tasks with max {self.max_workers} workers")

        self.task_queue = tasks.copy()
        start_time = time.time()

        try:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit tasks as they become ready
                future_to_task = {}

                while self.running and (len(self.completed_tasks) < len(tasks) or future_to_task):
                    # Get ready tasks
                    ready_tasks = self._get_ready_tasks()

                    # Submit new tasks up to worker limit
                    available_workers = self.max_workers - len(future_to_task)
                    for task in ready_tasks[:available_workers]:
                        future = executor.submit(self._execute_task, task)
                        future_to_task[future] = task
                        self.active_tasks[task.task_id] = None  # Mark as active
                        print(f"INFO: Submitted task {task.task_id} for execution")

                    # Wait for at least one task to complete
                    if future_to_task:
                        completed_futures = []
                        for future in as_completed(future_to_task, timeout=1.0):
                            completed_futures.append(future)
                            break

                        # Process completed tasks
                        for future in completed_futures:
                            task = future_to_task.pop(future)
                            try:
                                result = future.result()
                                self.completed_tasks[task.task_id] = result
                                status = "SUCCESS" if result.success else "FAILED"
                                print(f"INFO: Task {task.task_id} completed: {status}")
                                if not result.success:
                                    print(f"ERROR: {result.error_message}")
                            except Exception as e:
                                error_result = TaskResult(
                                    task_id=task.task_id,
                                    success=False,
                                    exit_code=1,
                                    evidence_dir=None,
                                    error_message=f"Executor error: {str(e)}",
                                    started_utc=datetime.datetime.now(datetime.UTC)
                                    .replace(microsecond=0)
                                    .isoformat()
                                    .replace("+00:00", "Z"),
                                    completed_utc=datetime.datetime.now(datetime.UTC)
                                    .replace(microsecond=0)
                                    .isoformat()
                                    .replace("+00:00", "Z"),
                                    execution_time_seconds=0,
                                )
                                self.completed_tasks[task.task_id] = error_result
                            finally:
                                if task.task_id in self.active_tasks:
                                    del self.active_tasks[task.task_id]

        except KeyboardInterrupt:
            print("\\nINFO: Parallel execution interrupted by user")

        total_time = time.time() - start_time
        successful_tasks = len([r for r in self.completed_tasks.values() if r.success])
        failed_tasks = len(self.completed_tasks) - successful_tasks

        print(f"\\nINFO: Parallel execution completed in {total_time:.2f} seconds")
        print(f"INFO: {successful_tasks} successful, {failed_tasks} failed out of {len(tasks)} total tasks")

        return self.completed_tasks


def load_tasks_from_manifest(manifest_path: Path) -> list[ParallelTask]:
    """Load parallel tasks from manifest file"""
    if not manifest_path.exists():
        raise ValueError(f"Manifest not found: {manifest_path}")

    try:
        if manifest_path.suffix.lower() in [".yml", ".yaml"]:
            import yaml

            data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        else:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))

        tasks = []
        for task_data in data.get("tasks", []):
            task = ParallelTask(
                task_id=task_data["task_id"],
                task_spec_path=Path(task_data["task_spec_path"]),
                agent_roles=task_data["agent_roles"],
                tool=task_data["tool"],
                priority=task_data.get("priority", 5),
                dependencies=task_data.get("dependencies", []),
                created_utc=task_data.get("created_utc", ""),
            )
            tasks.append(task)

        return tasks

    except Exception as e:
        raise ValueError(f"Invalid manifest file: {e}") from e


def create_example_manifest(output_path: Path):
    """Create example parallel execution manifest"""
    example = {
        "manifest_version": "4.1",
        "description": "Example SSID parallel execution manifest",
        "created_utc": datetime.datetime.now(datetime.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "tasks": [
            {
                "task_id": "example_planner_001",
                "task_spec_path": "24_meta_orchestration/registry/tasks/planner_task.json",
                "agent_roles": ["Planner"],
                "tool": "claude",
                "priority": 1,
                "dependencies": [],
            },
            {
                "task_id": "example_implementer_001",
                "task_spec_path": "24_meta_orchestration/registry/tasks/implementer_task.json",
                "agent_roles": ["Implementer"],
                "tool": "codex",
                "priority": 2,
                "dependencies": ["example_planner_001"],
            },
            {
                "task_id": "example_auditor_001",
                "task_spec_path": "24_meta_orchestration/registry/tasks/auditor_task.json",
                "agent_roles": ["ComplianceAuditor"],
                "tool": "gemini",
                "priority": 3,
                "dependencies": ["example_implementer_001"],
            },
        ],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(example, indent=2), encoding="utf-8")
    print(f"Example manifest created: {output_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="SSID Parallel Execution Framework v4.1")
    parser.add_argument("--manifest", help="Path to parallel execution manifest (JSON/YAML)")
    parser.add_argument("--task-spec", help="Single task spec to execute")
    parser.add_argument(
        "--tool",
        choices=["claude", "codex", "gemini", "kilo", "copilot", "opencode"],
        help="Tool for single task execution",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=MAX_CONCURRENT_TASKS,
        help=f"Maximum concurrent workers (default: {MAX_CONCURRENT_TASKS})",
    )
    parser.add_argument("--create-example", help="Create example manifest at specified path")
    parser.add_argument("--repo-root", help="Repository root (default: auto-detect)")

    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve() if args.repo_root else REPO_ROOT

    if args.create_example:
        create_example_manifest(Path(args.create_example))
        return 0

    try:
        executor = ParallelExecutor(repo_root, args.max_workers)

        if args.manifest:
            # Load tasks from manifest
            tasks = load_tasks_from_manifest(Path(args.manifest))
            results = executor.execute_parallel(tasks)
        elif args.task_spec and args.tool:
            # Single task execution
            task_spec = Path(args.task_spec)
            if not task_spec.exists():
                print(f"ERROR: Task spec not found: {task_spec}")
                return 1

            # Load task spec to get agent roles
            spec_data = executor._validate_task_spec(task_spec)
            task = ParallelTask(
                task_id=spec_data["task_id"],
                task_spec_path=task_spec,
                agent_roles=spec_data["agent_roles"],
                tool=args.tool,
                dependencies=[],
                priority=5,
            )

            results = executor.execute_parallel([task])
        else:
            print("ERROR: Must specify either --manifest or both --task-spec and --tool")
            parser.print_help()
            return 1

        # Summary
        successful = len([r for r in results.values() if r.success])
        total = len(results)
        print(f"\\nEXECUTION SUMMARY: {successful}/{total} tasks completed successfully")

        if successful == total:
            return 0
        else:
            return 1

    except Exception as e:
        print(f"ERROR: Parallel execution failed: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
