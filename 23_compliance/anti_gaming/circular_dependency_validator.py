#!/usr/bin/env python3
"""Circular Dependency Validator for SSID Root Modules.

Scans import statements across the 24 root modules to detect circular
dependency chains that would compromise architectural integrity.
A circular dependency is defined as A -> B -> ... -> A at the root-module level.
"""
from __future__ import annotations

import ast
import logging
import sys
from collections import defaultdict
from pathlib import Path

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]

ROOT_PREFIXES = [f"{i:02d}_" for i in range(1, 25)]


def extract_root_module(import_path: str) -> str | None:
    """Extract the SSID root module name from an import path.

    Example: '03_core.dispatcher' -> '03_core'
    """
    parts = import_path.split(".")
    if parts and any(parts[0].startswith(p) for p in ROOT_PREFIXES):
        return parts[0]
    return None


def build_dependency_graph() -> dict[str, set[str]]:
    """Build a root-module-level dependency graph by scanning Python imports."""
    graph: dict[str, set[str]] = defaultdict(set)

    for root_dir in REPO_ROOT.iterdir():
        if not root_dir.is_dir():
            continue
        if not any(root_dir.name.startswith(p) for p in ROOT_PREFIXES):
            continue

        source_root = root_dir.name

        for py_file in root_dir.rglob("*.py"):
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            except (SyntaxError, UnicodeDecodeError):
                continue

            for node in ast.walk(tree):
                targets: list[str] = []
                if isinstance(node, ast.Import):
                    targets = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    targets = [node.module]

                for target in targets:
                    dep_root = extract_root_module(target)
                    if dep_root and dep_root != source_root:
                        graph[source_root].add(dep_root)

    return dict(graph)


def find_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    """Detect all cycles in the dependency graph using DFS."""
    cycles: list[list[str]] = []
    visited: set[str] = set()
    stack: list[str] = []
    on_stack: set[str] = set()

    def dfs(node: str) -> None:
        visited.add(node)
        stack.append(node)
        on_stack.add(node)

        for neighbor in graph.get(node, set()):
            if neighbor not in visited:
                dfs(neighbor)
            elif neighbor in on_stack:
                idx = stack.index(neighbor)
                cycle = stack[idx:] + [neighbor]
                cycles.append(cycle)

        stack.pop()
        on_stack.discard(node)

    all_nodes = set(graph.keys())
    for deps in graph.values():
        all_nodes.update(deps)

    for node in sorted(all_nodes):
        if node not in visited:
            dfs(node)

    return cycles


def main() -> int:
    """Run circular dependency validation and report results."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    log.info("Building root-module dependency graph...")

    graph = build_dependency_graph()
    log.info("Found %d root modules with outgoing dependencies", len(graph))

    cycles = find_cycles(graph)

    if cycles:
        log.error("CIRCULAR_DEPENDENCY_FAIL: %d cycle(s) detected", len(cycles))
        for cycle in cycles:
            log.error("  Cycle: %s", " -> ".join(cycle))
        return 1

    log.info("CIRCULAR_DEPENDENCY_PASS: No cycles detected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
