#!/usr/bin/env python3
"""Generate markdown documentation from chart/module YAML files."""

import argparse
import json
import yaml
from pathlib import Path
from jinja2 import Template


def main():
    parser = argparse.ArgumentParser(description="Generate docs from chart YAML")
    parser.add_argument("--charts", required=True, help="Path to chart YAML file or directory")
    parser.add_argument("--template", required=True, help="Path to Jinja2 template")
    parser.add_argument("--out-dir", required=True, help="Output directory for generated docs")
    parser.add_argument("--out-manifest", required=True, help="Output manifest JSON")
    parser.add_argument("--repo-root", required=True, help="Repository root")

    args = parser.parse_args()

    charts_path = Path(args.charts)
    template_path = Path(args.template)
    out_dir = Path(args.out_dir)
    manifest_path = Path(args.out_manifest)

    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    # Load template
    if template_path.exists():
        template_content = template_path.read_text()
    else:
        # Default simple template
        template_content = """# {{ name }}

**Module ID:** {{ module_id }}
**Version:** {{ version }}
**Status:** {{ status }}

{{ description | default("No description provided.") }}
"""

    template = Template(template_content)

    charts = []
    generated_files = []

    # Process chart file
    if charts_path.is_file() and charts_path.suffix in [".yaml", ".yml"]:
        try:
            with open(charts_path, encoding="utf-8") as f:
                chart_data = yaml.safe_load(f)

            if not chart_data:
                result = {"status": "FAIL", "reason": "Empty YAML", "total_charts": 0}
                manifest_path.write_text(json.dumps(result, indent=2))
                return 1

            # Render template
            rendered = template.render(**chart_data)
            if not rendered.strip():
                result = {"status": "FAIL", "reason": "Empty render", "total_charts": 1}
                manifest_path.write_text(json.dumps(result, indent=2))
                return 1

            # Write output file
            module_id = chart_data.get("module_id", charts_path.stem)
            out_file = out_dir / f"{module_id}.md"
            out_file.write_text(rendered)
            generated_files.append(str(out_file))
            charts.append(chart_data)

        except Exception as e:
            result = {"status": "FAIL", "reason": str(e), "total_charts": 0}
            manifest_path.write_text(json.dumps(result, indent=2))
            return 1

    # Output manifest
    manifest = {
        "status": "PASS",
        "total_charts": len(charts),
        "generated_files": generated_files,
    }

    manifest_path.write_text(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
