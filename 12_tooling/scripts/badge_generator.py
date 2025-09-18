#!/usr/bin/env python3
"""
Badge Generator for SSID OpenCore Compliance
Version: 1.0
Date: 2025-09-16

Generates SVG badges for compliance, score, violations, and overrides.
"""

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path

class BadgeGenerator:
    def __init__(self):
        self.colors = {
            'green': '#4c1',
            'yellow': '#dfb317',
            'orange': '#fe7d37',
            'red': '#e05d44',
            'blue': '#007ec6',
            'lightgrey': '#9f9f9f'
        }

    def _get_score_color(self, score):
        """Determine color based on score"""
        if score >= 95:
            return self.colors['green']
        elif score >= 80:
            return self.colors['yellow']
        elif score >= 60:
            return self.colors['orange']
        else:
            return self.colors['red']

    def _get_compliance_status(self):
        """Get current compliance status"""
        try:
            # Run structure guard to get score
            result = subprocess.run(
                ['bash', '12_tooling/scripts/structure_guard.sh', 'score'],
                capture_output=True, text=True
            )
            score = int(result.stdout.strip())

            if score >= 95:
                return "COMPLIANT", self.colors['green'], score
            else:
                return "NON-COMPLIANT", self.colors['red'], score

        except Exception:
            return "UNKNOWN", self.colors['lightgrey'], 0

    def _create_svg_badge(self, label, message, color, output_path):
        """Create SVG badge with given parameters"""
        # Simple SVG badge template
        svg_template = f"""<svg xmlns="http://www.w3.org/2000/svg" width="104" height="20">
    <linearGradient id="b" x2="0" y2="100%">
        <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
        <stop offset="1" stop-opacity=".1"/>
    </linearGradient>
    <clipPath id="a">
        <rect width="104" height="20" rx="3" fill="#fff"/>
    </clipPath>
    <g clip-path="url(#a)">
        <path fill="#555" d="M0 0h63v20H0z"/>
        <path fill="{color}" d="M63 0h41v20H63z"/>
        <path fill="url(#b)" d="M0 0h104v20H0z"/>
    </g>
    <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="110">
        <text x="315" y="150" fill="#010101" fill-opacity=".3" transform="scale(.1)" textLength="530">{label}</text>
        <text x="315" y="140" transform="scale(.1)" textLength="530">{label}</text>
        <text x="825" y="150" fill="#010101" fill-opacity=".3" transform="scale(.1)" textLength="310">{message}</text>
        <text x="825" y="140" transform="scale(.1)" textLength="310">{message}</text>
    </g>
</svg>"""

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            f.write(svg_template)

        return output_path

    def generate_compliance_badge(self, output_path):
        """Generate compliance status badge"""
        status, color, score = self._get_compliance_status()
        return self._create_svg_badge("compliance", status, color, output_path)

    def generate_score_badge(self, output_path):
        """Generate score badge"""
        _, _, score = self._get_compliance_status()
        color = self._get_score_color(score)
        return self._create_svg_badge("score", f"{score}%", color, output_path)

    def generate_violations_badge(self, output_path):
        """Generate violations count badge"""
        # Check for violations in evidence logs
        violations_count = 0
        evidence_dir = Path("23_compliance/evidence/ci_runs")

        if evidence_dir.exists():
            for evidence_file in evidence_dir.glob("*_evidence_*.json"):
                try:
                    with open(evidence_file, 'r') as f:
                        evidence = json.load(f)
                        if 'violations' in evidence:
                            violations_count += len(evidence['violations'])
                except Exception:
                    continue

        color = self.colors['green'] if violations_count == 0 else self.colors['red']
        return self._create_svg_badge("violations", str(violations_count), color, output_path)

    def generate_overrides_badge(self, output_path):
        """Generate write overrides count badge"""
        overrides_count = 0
        registry_path = Path("23_compliance/evidence/write_override_registry.json")

        if registry_path.exists():
            try:
                with open(registry_path, 'r') as f:
                    registry = json.load(f)
                    overrides_count = registry.get('active_count', 0)
            except Exception:
                pass

        color = self.colors['green'] if overrides_count == 0 else self.colors['yellow']
        return self._create_svg_badge("overrides", str(overrides_count), color, output_path)

def main():
    parser = argparse.ArgumentParser(description="Generate compliance badges")
    parser.add_argument("--compliance", action="store_true", help="Generate compliance badge")
    parser.add_argument("--score", action="store_true", help="Generate score badge")
    parser.add_argument("--violations", action="store_true", help="Generate violations badge")
    parser.add_argument("--overrides", action="store_true", help="Generate overrides badge")
    parser.add_argument("--out", required=True, help="Output file path")

    args = parser.parse_args()

    generator = BadgeGenerator()

    if args.compliance:
        badge_path = generator.generate_compliance_badge(args.out)
        print(f"Compliance badge generated: {badge_path}")
    elif args.score:
        badge_path = generator.generate_score_badge(args.out)
        print(f"Score badge generated: {badge_path}")
    elif args.violations:
        badge_path = generator.generate_violations_badge(args.out)
        print(f"Violations badge generated: {badge_path}")
    elif args.overrides:
        badge_path = generator.generate_overrides_badge(args.out)
        print(f"Overrides badge generated: {badge_path}")
    else:
        print("Please specify badge type: --compliance, --score, --violations, or --overrides")

if __name__ == "__main__":
    main()