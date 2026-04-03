#!/usr/bin/env python3
"""phase1_materialize_charts_manifests.py -- Idempotent materializer for chart.yaml and manifest.yaml.

Creates chart.yaml and implementations/python/manifest.yaml for every shard
that is missing them. Does NOT overwrite existing files unless --repair flag is set.

MoSCoW capabilities use: MUST, SHOULD, COULD, WONT (never 'would').
"""
import argparse
import pathlib
import sys
import textwrap

REPO = pathlib.Path(__file__).resolve().parents[2]

CANONICAL_ROOTS = [
    "01_ai_layer", "02_audit_logging", "03_core", "04_deployment",
    "05_documentation", "06_data_pipeline", "07_governance_legal",
    "08_identity_score", "09_meta_identity", "10_interoperability",
    "11_test_simulation", "12_tooling", "13_ui_layer", "14_zero_time_auth",
    "15_infra", "16_codex", "17_observability", "18_data_layer",
    "19_adapters", "20_foundation", "21_post_quantum_crypto", "22_datasets",
    "23_compliance", "24_meta_orchestration",
]

SHARD_PREFIXES = [f"{i:02d}" for i in range(1, 17)]


def default_chart(root: str, shard_name: str) -> str:
    return textwrap.dedent(f"""\
        apiVersion: ssid/v1
        kind: ShardChart
        metadata:
          root: {root}
          shard: {shard_name}
        capabilities:
          - MUST: baseline structure conformance
          - SHOULD: implementation stubs
          - COULD: extended integration
          - WONT: deprecated legacy support
    """)


def default_manifest(root: str, shard_name: str) -> str:
    return textwrap.dedent(f"""\
        apiVersion: ssid/v1
        kind: ShardManifest
        metadata:
          root: {root}
          shard: {shard_name}
          language: python
        status: stub
        files: []
    """)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repair", action="store_true", help="Overwrite existing files (requires SAFE-FIX)")
    args = parser.parse_args()

    created = 0
    skipped = 0
    for root in CANONICAL_ROOTS:
        shards_dir = REPO / root / "shards"
        if not shards_dir.is_dir():
            continue
        for sd in sorted(shards_dir.iterdir()):
            if not sd.is_dir() or not sd.name[:2].isdigit():
                continue
            chart = sd / "chart.yaml"
            manifest = sd / "implementations" / "python" / "manifest.yaml"
            for fpath, content_fn in [(chart, default_chart), (manifest, default_manifest)]:
                if fpath.is_file() and not args.repair:
                    skipped += 1
                    continue
                fpath.parent.mkdir(parents=True, exist_ok=True)
                fpath.write_text(content_fn(root, sd.name), encoding="utf-8")
                created += 1

    print(f"Created: {created}, Skipped (existing): {skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
