#!/usr/bin/env python3
"""Collect unanchored evidence files for Merkle tree anchoring."""

import argparse
import json
from pathlib import Path
from datetime import datetime


def main():
    parser = argparse.ArgumentParser(description="Collect unanchored evidence files")
    parser.add_argument("--since-last-anchor", required=True, help="Path to anchor state file")
    parser.add_argument("--agent-runs-dir", required=True, help="Directory with agent runs")
    parser.add_argument("--out", required=True, help="Output JSON file path")

    args = parser.parse_args()

    agent_runs_dir = Path(args.agent_runs_dir)
    state_file = Path(args.since_last_anchor)

    # Load last anchor timestamp
    last_anchor_ts = None
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text())
            last_anchor_ts = state.get("last_anchor_ts")
        except Exception:
            pass

    # Collect unanchored evidence entries
    entries = []
    for run_dir in agent_runs_dir.glob("run-*"):
        evidence_file = run_dir / "evidence.jsonl"
        if not evidence_file.exists():
            continue

        for line in evidence_file.read_text().strip().split("\n"):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                # Simple timestamp-based filtering (stub implementation)
                entries.append(entry)
            except json.JSONDecodeError:
                pass

    result = {
        "total_unanchored": len(entries),
        "entries": entries,
        "collected_at": datetime.utcnow().isoformat() + "Z",
    }

    output_file = Path(args.out)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(result, indent=2))

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
