#!/usr/bin/env python3
"""
README Badge Updater
Version: 1.0
Date: 2025-09-16

Updates README.md with compliance badges and scores.
"""

import argparse
import re
from pathlib import Path

class ReadmeBadgeUpdater:
    def __init__(self):
        self.badge_section_marker = "<!-- SSID-COMPLIANCE-BADGES -->"

    def update_readme_badges(self, readme_path, compliance_badge=None, score_badge=None):
        """Update README with compliance badges"""
        readme_file = Path(readme_path)

        if not readme_file.exists():
            print(f"README file not found: {readme_path}")
            return False

        # Read current README content
        with open(readme_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Create badge HTML
        badge_html = self._create_badge_html(compliance_badge, score_badge)

        # Check if badge section exists
        if self.badge_section_marker in content:
            # Replace existing badge section
            pattern = rf'{re.escape(self.badge_section_marker)}.*?{re.escape(self.badge_section_marker)}'
            new_content = re.sub(
                pattern,
                f'{self.badge_section_marker}\n{badge_html}\n{self.badge_section_marker}',
                content,
                flags=re.DOTALL
            )
        else:
            # Add badge section at the top after the title
            lines = content.split('\n')
            insert_index = 0

            # Find a good place to insert (after title)
            for i, line in enumerate(lines):
                if line.startswith('#') and not line.startswith('##'):
                    insert_index = i + 1
                    break

            # Insert badge section
            badge_section = [
                '',
                self.badge_section_marker,
                badge_html.strip(),
                self.badge_section_marker,
                ''
            ]

            lines[insert_index:insert_index] = badge_section
            new_content = '\n'.join(lines)

        # Write updated content
        with open(readme_file, 'w', encoding='utf-8') as f:
            f.write(new_content)

        print(f"README badges updated: {readme_file}")
        return True

    def _create_badge_html(self, compliance_badge=None, score_badge=None):
        """Create HTML for badges"""
        badges = []

        if compliance_badge:
            badges.append(f'![Compliance]({compliance_badge})')

        if score_badge:
            badges.append(f'![Score]({score_badge})')

        # Add some additional static badges
        badges.extend([
            '![SSID](https://img.shields.io/badge/SSID-OpenCore-blue)',
            '![Security](https://img.shields.io/badge/Security-Enhanced-green)',
            '![Structure](https://img.shields.io/badge/Structure-24--Module-orange)'
        ])

        return ' '.join(badges)

def main():
    parser = argparse.ArgumentParser(description="Update README with compliance badges")
    parser.add_argument("--in", dest="input_file", required=True, help="Input README file")
    parser.add_argument("--badge", help="Compliance badge file")
    parser.add_argument("--score", help="Score badge file")
    parser.add_argument("--out", required=True, help="Output README file")

    args = parser.parse_args()

    updater = ReadmeBadgeUpdater()

    # Convert badge paths to relative paths for markdown
    compliance_badge = None
    score_badge = None

    if args.badge:
        compliance_badge = Path(args.badge).relative_to(Path.cwd())

    if args.score:
        score_badge = Path(args.score).relative_to(Path.cwd())

    success = updater.update_readme_badges(
        args.input_file,
        compliance_badge,
        score_badge
    )

    if success and args.out != args.input_file:
        # Copy to output if different
        import shutil
        shutil.copy(args.input_file, args.out)
        print(f"Updated README copied to: {args.out}")

if __name__ == "__main__":
    main()