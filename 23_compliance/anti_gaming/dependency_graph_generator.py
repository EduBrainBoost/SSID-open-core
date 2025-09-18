#!/usr/bin/env python3
"""
Dependency Graph Generator
Generates visual dependency graphs for transparency
Version: 1.0
Date: 2025-09-15
"""

import os
import sys
import json
import networkx as nx
from pathlib import Path
from datetime import datetime


class DependencyGraphGenerator:
    """Generates dependency graphs in multiple formats"""

    def __init__(self):
        self.root_dir = Path(__file__).parent.parent.parent
        self.graph = nx.DiGraph()
        self.output_dir = self.root_dir / "23_compliance/anti_gaming/dependency_maps"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def build_compliance_graph(self):
        """Build graph of compliance-related dependencies"""
        # Add key compliance components
        components = {
            "structure_guard": "12_tooling/scripts/structure_guard.sh",
            "pre_commit_hook": "12_tooling/hooks/pre_commit/structure_validation.sh",
            "ci_gate": "24_meta_orchestration/triggers/ci/gates/structure_lock_l3.py",
            "policy": "23_compliance/policies/structure_policy.yaml",
            "exceptions": "23_compliance/exceptions/structure_exceptions.yaml",
            "tests": "23_compliance/tests/unit/test_structure_policy_vs_md.py",
            "circular_validator": "23_compliance/anti_gaming/circular_dependency_validator.py",
            "badge_checker": "23_compliance/anti_gaming/badge_integrity_checker.sh",
            "blueprint": "24_meta_orchestration/registry/logs/SSID_opencore_structure_level3.md"
        }

        # Add nodes
        for name, path in components.items():
            self.graph.add_node(name, path=path, type="compliance_component")

        # Add dependencies
        self.graph.add_edge("pre_commit_hook", "structure_guard")
        self.graph.add_edge("ci_gate", "structure_guard")
        self.graph.add_edge("structure_guard", "policy")
        self.graph.add_edge("tests", "policy")
        self.graph.add_edge("ci_gate", "badge_checker")
        self.graph.add_edge("badge_checker", "structure_guard")
        self.graph.add_edge("circular_validator", "structure_guard")
        self.graph.add_edge("policy", "blueprint")

        # Add module dependencies
        modules = [
            "01_ai_layer", "02_audit_logging", "03_core", "04_deployment",
            "05_documentation", "06_data_pipeline", "07_governance_legal",
            "08_identity_score", "09_meta_identity", "10_interoperability",
            "11_test_simulation", "12_tooling", "13_ui_layer", "14_zero_time_auth",
            "15_infra", "16_codex", "17_observability", "18_data_layer",
            "19_adapters", "20_foundation", "21_post_quantum_crypto",
            "22_datasets", "23_compliance", "24_meta_orchestration"
        ]

        for module in modules:
            self.graph.add_node(module, type="module")
            self.graph.add_edge("structure_guard", module)

    def export_dot(self):
        """Export graph in DOT format"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = self.output_dir / f"compliance_dependencies_{timestamp}.dot"

        with open(output_file, 'w') as f:
            f.write("digraph compliance_dependencies {\n")
            f.write("  rankdir=TB;\n")
            f.write("  node [shape=box, style=rounded];\n")

            # Write nodes
            for node, data in self.graph.nodes(data=True):
                if data.get('type') == 'compliance_component':
                    f.write(f'  "{node}" [color=red, style="rounded,filled", fillcolor=lightcoral];\n')
                elif data.get('type') == 'module':
                    f.write(f'  "{node}" [color=blue, style="rounded,filled", fillcolor=lightblue];\n')
                else:
                    f.write(f'  "{node}";\n')

            # Write edges
            for source, target in self.graph.edges():
                f.write(f'  "{source}" -> "{target}";\n')

            f.write("}\n")

        return output_file

    def export_json(self):
        """Export graph in JSON format"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = self.output_dir / f"compliance_dependencies_{timestamp}.json"

        graph_data = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "generator": "dependency_graph_generator.py",
                "version": "1.0"
            },
            "nodes": [
                {
                    "id": node,
                    "type": data.get('type', 'unknown'),
                    "path": data.get('path', '')
                }
                for node, data in self.graph.nodes(data=True)
            ],
            "edges": [
                {"source": source, "target": target}
                for source, target in self.graph.edges()
            ],
            "statistics": {
                "node_count": len(self.graph.nodes()),
                "edge_count": len(self.graph.edges()),
                "is_acyclic": nx.is_directed_acyclic_graph(self.graph)
            }
        }

        with open(output_file, 'w') as f:
            json.dump(graph_data, f, indent=2)

        return output_file

    def export_svg(self):
        """Export graph in SVG format (requires graphviz)"""
        try:
            import pygraphviz as pgv

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            dot_file = self.export_dot()
            svg_file = self.output_dir / f"compliance_dependencies_{timestamp}.svg"

            # Convert DOT to SVG
            graph = pgv.AGraph(str(dot_file))
            graph.draw(str(svg_file), format='svg', prog='dot')

            return svg_file

        except ImportError:
            print("Warning: pygraphviz not available, skipping SVG export")
            return None

    def export_graph(self):
        """Export graph in all available formats"""
        results = {}

        print("Generating compliance dependency graphs...")

        self.build_compliance_graph()

        # Export in multiple formats
        results['json'] = self.export_json()
        results['dot'] = self.export_dot()

        svg_file = self.export_svg()
        if svg_file:
            results['svg'] = svg_file

        return results

    def generate_report(self):
        """Generate dependency analysis report"""
        self.build_compliance_graph()

        report = {
            "analysis_date": datetime.now().isoformat(),
            "total_nodes": len(self.graph.nodes()),
            "total_edges": len(self.graph.edges()),
            "is_acyclic": nx.is_directed_acyclic_graph(self.graph),
            "strongly_connected_components": len(list(nx.strongly_connected_components(self.graph))),
            "compliance_components": len([n for n, d in self.graph.nodes(data=True)
                                        if d.get('type') == 'compliance_component']),
            "modules": len([n for n, d in self.graph.nodes(data=True)
                          if d.get('type') == 'module'])
        }

        return report


def export_graph():
    """Main function for graph export"""
    generator = DependencyGraphGenerator()
    results = generator.export_graph()

    print("Dependency graphs generated:")
    for format_type, file_path in results.items():
        print(f"  {format_type.upper()}: {file_path}")

    # Generate report
    report = generator.generate_report()
    print(f"\nGraph Analysis:")
    print(f"  Nodes: {report['total_nodes']}")
    print(f"  Edges: {report['total_edges']}")
    print(f"  Acyclic: {report['is_acyclic']}")
    print(f"  Compliance Components: {report['compliance_components']}")
    print(f"  Modules: {report['modules']}")

    return results


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--export-all-formats":
        export_graph()
    else:
        generator = DependencyGraphGenerator()
        results = generator.export_graph()
        print("Dependency graphs exported successfully")