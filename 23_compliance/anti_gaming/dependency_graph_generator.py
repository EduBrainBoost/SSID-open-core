#!/usr/bin/env python3
"""Dependency Graph Generator for SSID Root Modules.

Generates a dependency graph in DOT format showing inter-root-module
dependencies. Uses the same import scanning as circular_dependency_validator
but outputs a visualization-ready graph.

Output formats: DOT (Graphviz), JSON adjacency list.
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]

# Reuse the graph builder from circular_dependency_validator
VALIDATOR_PATH = Path(__file__).parent / "circular_dependency_validator.py"


def _import_validator():
    """Import circular_dependency_validator dynamically."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("circular_dependency_validator", VALIDATOR_PATH)
    if not spec or not spec.loader:
        raise ImportError(f"Cannot load {VALIDATOR_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def generate_dot(graph: dict[str, set[str]]) -> str:
    """Generate DOT format string from dependency graph."""
    lines = ["digraph ssid_dependencies {"]
    lines.append('    rankdir=LR;')
    lines.append('    node [shape=box, style=filled, fillcolor="#e8f4fd"];')
    lines.append("")

    all_nodes = set(graph.keys())
    for deps in graph.values():
        all_nodes.update(deps)

    for node in sorted(all_nodes):
        label = node.replace("_", "\\n", 1)
        lines.append(f'    "{node}" [label="{label}"];')

    lines.append("")

    for source in sorted(graph.keys()):
        for target in sorted(graph[source]):
            lines.append(f'    "{source}" -> "{target}";')

    lines.append("}")
    return "\n".join(lines)


def generate_json(graph: dict[str, set[str]]) -> str:
    """Generate JSON adjacency list from dependency graph."""
    serializable = {k: sorted(v) for k, v in sorted(graph.items())}
    return json.dumps(serializable, indent=2)


def main() -> int:
    """Generate and output dependency graph."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    validator = _import_validator()
    graph = validator.build_dependency_graph()

    log.info("Dependency graph: %d modules, %d edges",
             len(graph), sum(len(v) for v in graph.values()))

    output_dir = REPO_ROOT / "23_compliance" / "anti_gaming" / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    dot_path = output_dir / "dependency_graph.dot"
    dot_path.write_text(generate_dot(graph), encoding="utf-8")
    log.info("DOT graph written to %s", dot_path)

    json_path = output_dir / "dependency_graph.json"
    json_path.write_text(generate_json(graph), encoding="utf-8")
    log.info("JSON graph written to %s", json_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
