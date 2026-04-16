#!/usr/bin/env python3
"""Generate documentation from YAML configs."""

import argparse
import json
import yaml
from pathlib import Path


def render_chart_yaml_to_markdown(chart_yaml_path: Path) -> str:
    """Convert Chart.yaml to markdown documentation."""
    try:
        with open(chart_yaml_path, encoding="utf-8") as f:
            chart_data = yaml.safe_load(f)
    except Exception:
        return None

    if not chart_data:
        return None

    md = []
    md.append(f"# {chart_data.get('name', 'Chart')}")
    md.append(f"\nVersion: {chart_data.get('version', 'unknown')}")
    md.append(f"Description: {chart_data.get('description', 'No description')}\n")

    if chart_data.get("maintainers"):
        md.append("## Maintainers\n")
        for m in chart_data["maintainers"]:
            md.append(f"- {m.get('name', 'Unknown')}\n")

    if chart_data.get("dependencies"):
        md.append("## Dependencies\n")
        for d in chart_data["dependencies"]:
            md.append(f"- {d.get('name', 'Unknown')} ({d.get('version', 'unknown')})\n")

    return "\n".join(md)


def main():
    parser = argparse.ArgumentParser(description="Generate documentation")
    parser.add_argument("--input", required=True, help="Input YAML file")
    parser.add_argument("--out", required=True, help="Output markdown file")

    args = parser.parse_args()

    input_file = Path(args.input)
    if not input_file.exists():
        return 1

    markdown = render_chart_yaml_to_markdown(input_file)
    if markdown is None:
        return 1

    output_file = Path(args.out)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(markdown)

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
