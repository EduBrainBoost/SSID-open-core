#!/usr/bin/env python3
"""
create_sot_fusion.py — Merge the 6 canonical SoT source files into a
deduplicated master output.

Reads the source manifest from 16_codex/sot_master_merged.json, loads each
source file, deduplicates on a line-by-line basis, and writes:
  - sot_fusion_output.md   (merged text)
  - sot_fusion_stats.json  (merge statistics + SHA-256)

Usage:
    python create_sot_fusion.py --output <directory>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def find_codex_root(start: Path | None = None) -> Path:
    """Locate 16_codex relative to this script or CWD."""
    candidates = [
        Path(__file__).resolve().parent.parent,          # 16_codex/tools -> 16_codex
        (start or Path.cwd()),
    ]
    for c in candidates:
        if c.name == "16_codex" and c.is_dir():
            return c
        maybe = c / "16_codex"
        if maybe.is_dir():
            return maybe
    sys.exit("ERROR: Cannot locate 16_codex directory.")


def load_manifest(codex: Path) -> list[dict]:
    """Return the source list from sot_master_merged.json."""
    manifest_path = codex / "sot_master_merged.json"
    if not manifest_path.exists():
        sys.exit(f"ERROR: Manifest not found at {manifest_path}")
    with open(manifest_path, encoding="utf-8") as fh:
        data = json.load(fh)
    return data.get("sources", [])


def read_source(codex: Path, source: dict) -> list[str]:
    """Read a single SoT source file and return its lines."""
    rel = source.get("path", "").replace("\\", "/")
    # path is relative to 16_codex parent (repo root) or 16_codex itself
    full = codex / source["file"]
    if not full.exists():
        full = codex.parent / rel
    if not full.exists():
        print(f"WARNING: Source not found: {full}", file=sys.stderr)
        return []
    with open(full, encoding="utf-8") as fh:
        return fh.readlines()


def deduplicate_lines(all_lines: list[str]) -> list[str]:
    """Remove exact duplicate lines while preserving first-seen order."""
    seen: set[str] = set()
    result: list[str] = []
    for line in all_lines:
        key = line.rstrip("\n\r")
        if key not in seen:
            seen.add(key)
            result.append(line)
    return result


def sha256_of(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Merge canonical SoT sources.")
    parser.add_argument("--output", required=True, help="Output directory")
    args = parser.parse_args(argv)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    codex = find_codex_root()
    sources = load_manifest(codex)
    if not sources:
        sys.exit("ERROR: No sources found in manifest.")

    all_lines: list[str] = []
    per_source_stats: list[dict] = []

    for src in sources:
        lines = read_source(codex, src)
        per_source_stats.append({
            "file": src["file"],
            "lines_raw": len(lines),
        })
        all_lines.extend(lines)

    total_raw = len(all_lines)
    deduped = deduplicate_lines(all_lines)
    total_deduped = len(deduped)

    merged_text = "".join(deduped)
    output_hash = sha256_of(merged_text)

    # Write fusion output
    fusion_path = output_dir / "sot_fusion_output.md"
    with open(fusion_path, "w", encoding="utf-8") as fh:
        fh.write(merged_text)

    # Write stats
    stats = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_count": len(sources),
        "total_lines_raw": total_raw,
        "total_lines_deduped": total_deduped,
        "lines_removed": total_raw - total_deduped,
        "dedup_ratio": round((total_raw - total_deduped) / max(total_raw, 1), 4),
        "sha256_output": output_hash,
        "per_source": per_source_stats,
    }
    stats_path = output_dir / "sot_fusion_stats.json"
    with open(stats_path, "w", encoding="utf-8") as fh:
        json.dump(stats, fh, indent=2)

    print(f"Fusion complete: {total_deduped} unique lines from {total_raw} raw lines.")
    print(f"Output:  {fusion_path}")
    print(f"Stats:   {stats_path}")
    print(f"SHA-256: {output_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
