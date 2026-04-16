#!/usr/bin/env python3
"""Collect unanchored evidence files for Merkle tree anchoring."""

import argparse
import hashlib
import json
from pathlib import Path
from datetime import datetime, UTC


def main():
    parser = argparse.ArgumentParser(description="Collect unanchored evidence files")
    parser.add_argument("--since-last-anchor", required=True, help="Path to anchor state file")
    parser.add_argument("--agent-runs-dir", required=True, help="Directory with agent runs")
    parser.add_argument("--out", required=True, help="Output JSON file path")

    args = parser.parse_args()

    agent_runs_dir = Path(args.agent_runs_dir)
    state_file = Path(args.since_last_anchor)

    # Load anchored hashes for deduplication
    anchored_hashes = set()
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text())
            anchored_hashes = set(state.get("anchored_hashes", []))
        except Exception:
            pass

    # Collect unanchored evidence entries
    entries = []
    for run_dir in agent_runs_dir.glob("run-*"):
        evidence_file = run_dir / "evidence.jsonl"
        if not evidence_file.exists():
            continue

        # Calculate file hash for deduplication
        file_hash = hashlib.sha256(evidence_file.read_bytes()).hexdigest()

        # Skip if already anchored
        if file_hash in anchored_hashes:
            continue

        for line in evidence_file.read_text().strip().split("\n"):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                # Add run_id from directory name
                run_id = run_dir.name
                entry["run_id"] = run_id
                entries.append(entry)
            except json.JSONDecodeError:
                pass

    result = {
        "total_unanchored": len(entries),
        "entries": entries,
        "collected_at": datetime.now(UTC).isoformat() + "Z",
    }

    output_file = Path(args.out)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(result, indent=2))

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
