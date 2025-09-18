#!/usr/bin/env python3
"""
Circular Dependency Validator
Prevents circular references in badge logic and validation scripts
Version: 1.0
Date: 2025-09-15
"""

import os
import sys
import json
import networkx as nx
from pathlib import Path
from datetime import datetime


class CircularValidator:
    """Validates against circular dependencies in compliance logic"""

    def __init__(self):
        self.root_dir = Path(__file__).parent.parent.parent
        self.graph = nx.DiGraph()
        self.dependencies = {}
        self.circular_deps = []

    def scan_dependencies(self):
        """Scan all validation scripts for dependencies"""
        script_dirs = [
            "12_tooling/scripts",
            "12_tooling/hooks",
            "23_compliance/anti_gaming",
            "24_meta_orchestration/triggers/ci/gates"
        ]

        for script_dir in script_dirs:
            dir_path = self.root_dir / script_dir
            if dir_path.exists():
                self._scan_directory(dir_path)

    def _scan_directory(self, directory):
        """Scan a directory for script dependencies"""
        for file_path in directory.rglob("*"):
            if file_path.is_file() and file_path.suffix in ['.py', '.sh', '.yaml', '.yml']:
                self._analyze_file(file_path)

    def _analyze_file(self, file_path):
        """Analyze a file for dependencies"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            file_name = str(file_path.relative_to(self.root_dir))
            dependencies = []

            # Look for script calls, imports, includes
            lines = content.split('\n')
            for line in lines:
                line = line.strip()

                # Python imports
                if line.startswith('import ') or line.startswith('from '):
                    dependencies.append(f"python_import: {line}")

                # Shell script calls
                if '.sh' in line and ('$ROOT_DIR' in line or './' in line):
                    dependencies.append(f"shell_call: {line}")

                # YAML references
                if 'path:' in line or 'script:' in line:
                    dependencies.append(f"yaml_ref: {line}")

            if dependencies:
                self.dependencies[file_name] = dependencies
                self._add_to_graph(file_name, dependencies)

        except Exception as e:
            print(f"Warning: Could not analyze {file_path}: {e}")

    def _add_to_graph(self, file_name, dependencies):
        """Add file and dependencies to graph"""
        self.graph.add_node(file_name)

        for dep in dependencies:
            # Simplified dependency extraction
            if 'structure_guard' in dep:
                self.graph.add_edge(file_name, '12_tooling/scripts/structure_guard.sh')
            elif 'structure_validation' in dep:
                self.graph.add_edge(file_name, '12_tooling/hooks/pre_commit/structure_validation.sh')
            elif 'structure_lock_l3' in dep:
                self.graph.add_edge(file_name, '24_meta_orchestration/triggers/ci/gates/structure_lock_l3.py')

    def detect_circular_dependencies(self):
        """Detect circular dependencies in the graph"""
        try:
            cycles = list(nx.simple_cycles(self.graph))
            self.circular_deps = cycles
            return len(cycles) == 0
        except Exception as e:
            print(f"Error detecting cycles: {e}")
            return True

    def export_graph(self, format_type="json"):
        """Export dependency graph"""
        output_dir = self.root_dir / "23_compliance/anti_gaming/dependency_maps"
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        if format_type == "json":
            output_file = output_dir / f"dependencies_{timestamp}.json"
            graph_data = {
                "nodes": list(self.graph.nodes()),
                "edges": list(self.graph.edges()),
                "dependencies": self.dependencies,
                "circular_dependencies": self.circular_deps
            }
            with open(output_file, 'w') as f:
                json.dump(graph_data, f, indent=2)

        elif format_type == "dot":
            output_file = output_dir / f"dependencies_{timestamp}.dot"
            nx.nx_pydot.write_dot(self.graph, output_file)

        return output_file

    def validate(self):
        """Run complete validation"""
        print("SSID OpenCore - Circular Dependency Validator")
        print("=" * 50)

        self.scan_dependencies()
        is_valid = self.detect_circular_dependencies()

        print(f"Files analyzed: {len(self.dependencies)}")
        print(f"Dependencies found: {sum(len(deps) for deps in self.dependencies.values())}")

        if is_valid:
            print("✅ No circular dependencies detected")
        else:
            print(f"❌ {len(self.circular_deps)} circular dependencies found:")
            for i, cycle in enumerate(self.circular_deps, 1):
                print(f"  {i}. {' -> '.join(cycle)} -> {cycle[0]}")

        # Export graph
        export_file = self.export_graph()
        print(f"Dependency graph exported to: {export_file}")

        return is_valid


if __name__ == "__main__":
    validator = CircularValidator()

    if len(sys.argv) > 1 and sys.argv[1] == "--export-graph":
        validator.scan_dependencies()
        for fmt in ["json", "dot"]:
            output = validator.export_graph(fmt)
            print(f"Exported {fmt}: {output}")
    else:
        is_valid = validator.validate()
        sys.exit(0 if is_valid else 1)