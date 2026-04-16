#!/usr/bin/env python3
"""Build Merkle tree from evidence entries for anchoring."""

import argparse
import hashlib
import json
from pathlib import Path


def merkle_hash(data: str) -> str:
    """Compute SHA256 hash for Merkle tree."""
    return hashlib.sha256(data.encode()).hexdigest()


def build_merkle_root(entries: list) -> str:
    """Build Merkle tree root from entries."""
    if not entries:
        return None

    # Convert entries to hashable strings
    hashes = [merkle_hash(json.dumps(e, sort_keys=True)) for e in entries]

    # Build tree bottom-up
    while len(hashes) > 1:
        if len(hashes) % 2:
            hashes.append(hashes[-1])  # Duplicate last hash if odd
        new_hashes = []
        for i in range(0, len(hashes), 2):
            combined = hashes[i] + hashes[i + 1]
            new_hashes.append(merkle_hash(combined))
        hashes = new_hashes

    return hashes[0] if hashes else None


def main():
    parser = argparse.ArgumentParser(description="Build Merkle tree from evidence")
    parser.add_argument("--input", required=True, help="Input collected evidence JSON")
    parser.add_argument("--out", required=True, help="Output Merkle tree JSON")
    parser.add_argument("--blockchain-url", required=False, help="Blockchain API URL for anchoring")

    args = parser.parse_args()

    input_file = Path(args.input)
    if not input_file.exists():
        return 1

    data = json.loads(input_file.read_text())
    entries = data.get("entries", [])

    root = build_merkle_root(entries)

    # Blockchain anchoring (stub - always fails gracefully)
    tx_hash = None
    blockchain_attempted = args.blockchain_url is not None
    dry_run = args.blockchain_url is None

    result = {
        "empty": len(entries) == 0,
        "root": root,
        "total_entries": len(entries),
        "tx_hash": tx_hash,
        "blockchain_attempted": blockchain_attempted,
        "dry_run": dry_run,
    }

    output_file = Path(args.out)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(result, indent=2))

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
