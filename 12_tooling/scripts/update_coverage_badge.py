#!/usr/bin/env python3
"""Update coverage badge — computes and updates the test coverage badge data."""
from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone


def update_coverage_badge(repo_root: Path | str = ".") -> dict:
    root = Path(repo_root)
    tests_dir = root / "tests"
    simulation_dir = root / "11_test_simulation"

    total_tests = 0
    passed_tests = 0
    test_files = list(tests_dir.rglob("test_*.py")) + list(simulation_dir.rglob("test_*.py"))

    for tf in test_files:
        content = tf.read_text(encoding="utf-8", errors="ignore")
        # Count test functions/classes
        import re
        test_funcs = re.findall(r'def test_\w+', content)
        total_tests += len(test_funcs)

    badge = {
        "badge": "coverage",
        "value": f"{total_tests} tests",
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
        "test_files": [str(f.relative_to(root)) for f in test_files],
    }

    badge_path = root / "17_observability" / "score" / "coverage_badge.json"
    badge_path.parent.mkdir(parents=True, exist_ok=True)
    badge_path.write_text(json.dumps(badge, indent=2), encoding="utf-8")

    return badge


if __name__ == "__main__":
    import sys
    repo = sys.argv[1] if len(sys.argv) > 1 else "."
    badge = update_coverage_badge(repo)
    print(json.dumps(badge, indent=2))
