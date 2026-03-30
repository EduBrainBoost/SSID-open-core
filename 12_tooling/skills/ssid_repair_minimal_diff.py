"""ssid-repair-minimal-diff — Minimal-diff repair logic.

Validates that a proposed change set is minimal: only changed lines
are modified, no unrelated additions or deletions.
"""

import hashlib
from typing import Dict, List

from ._evidence import make_evidence, result

SKILL_ID = "ssid-repair-minimal-diff"


def _compute_diff_stats(before_lines: List[str], after_lines: List[str]) -> Dict:
    """Compute simple line-level diff statistics."""
    added = 0
    removed = 0
    unchanged = 0

    before_set = {}
    for i, line in enumerate(before_lines):
        before_set.setdefault(line, []).append(i)

    after_set = {}
    for i, line in enumerate(after_lines):
        after_set.setdefault(line, []).append(i)

    for line in set(list(before_set.keys()) + list(after_set.keys())):
        b_count = len(before_set.get(line, []))
        a_count = len(after_set.get(line, []))
        common = min(b_count, a_count)
        unchanged += common
        removed += max(0, b_count - common)
        added += max(0, a_count - common)

    return {"added": added, "removed": removed, "unchanged": unchanged}


def execute(context: Dict) -> Dict:
    """Validate that a repair diff is minimal.

    context must contain:
        before_content: str  — file content before repair
        after_content: str   — file content after repair
    Optional:
        max_change_ratio: float  — max allowed (added+removed)/total, default 0.5
    """
    before = context.get("before_content")
    after = context.get("after_content")

    if before is None or after is None:
        ev = make_evidence(SKILL_ID, "FAIL", {"reason": "before_content and after_content required"})
        return result("FAIL", ev, "before_content and after_content are required")

    max_ratio = context.get("max_change_ratio", 0.5)
    before_lines = before.splitlines()
    after_lines = after.splitlines()

    stats = _compute_diff_stats(before_lines, after_lines)
    total = stats["added"] + stats["removed"] + stats["unchanged"]
    change_ratio = (stats["added"] + stats["removed"]) / max(total, 1)

    sha_before = hashlib.sha256(before.encode("utf-8")).hexdigest()
    sha_after = hashlib.sha256(after.encode("utf-8")).hexdigest()

    details = {
        "stats": stats,
        "total_lines": total,
        "change_ratio": round(change_ratio, 4),
        "max_change_ratio": max_ratio,
        "sha256_before": sha_before,
        "sha256_after": sha_after,
    }

    if change_ratio > max_ratio:
        ev = make_evidence(SKILL_ID, "FAIL", details, sha256_before=sha_before, sha256_after=sha_after)
        return result("FAIL", ev, f"Change ratio {change_ratio:.2%} exceeds max {max_ratio:.2%}")

    ev = make_evidence(SKILL_ID, "PASS", details, sha256_before=sha_before, sha256_after=sha_after)
    return result("PASS", ev, f"Minimal diff confirmed: {change_ratio:.2%} changed")
