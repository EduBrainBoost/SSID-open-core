#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from _lib.shards import ROOTS_24, SHARDS_16
from chart_manifest_bootstrap import ensure_contract_pack


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate deterministic minimum conformance fixtures for all shards.")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    summary = {"contracts_created": 0, "fixtures_created": 0, "indexes_created": 0, "readmes_created": 0}
    for root_name in ROOTS_24:
        for shard_name in SHARDS_16:
            shard_dir = repo_root / root_name / "shards" / shard_name
            shard_dir.mkdir(parents=True, exist_ok=True)
            ensure_contract_pack(shard_dir, root_name, shard_name, summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
