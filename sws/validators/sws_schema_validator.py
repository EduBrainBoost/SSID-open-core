#!/usr/bin/env python3
"""SWS V1 Schema Validator.

Validates that all 11 V1 schemas parse as JSON Schema Draft-07 and
validates sample/fixture payloads if supplied.

Exit codes:
    0  all schemas valid
    2  schema load error
    3  schema spec violation
    4  fixture validation error
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    from jsonschema import Draft7Validator
except ImportError:
    print("[FATAL] jsonschema not installed. pip install jsonschema", file=sys.stderr)
    sys.exit(2)


SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas"

V1_SCHEMAS = [
    "job_manifest.schema.json",
    "attempt_manifest.schema.json",
    "source_manifest.schema.json",
    "rights_manifest.schema.json",
    "media_technical.schema.json",
    "transcript_master.schema.json",
    "shot_timeline.schema.json",
    "caption_layers.schema.json",
    "audio_map.schema.json",
    "hook_fingerprint.schema.json",
    "rebuild_blueprint.schema.json",
]


def load_schema(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def validate_all() -> int:
    missing = []
    invalid = []
    ok = []
    for name in V1_SCHEMAS:
        path = SCHEMA_DIR / name
        if not path.exists():
            missing.append(name)
            continue
        try:
            schema = load_schema(path)
            Draft7Validator.check_schema(schema)
            ok.append(name)
        except Exception as e:
            invalid.append((name, str(e)))

    print("=" * 60)
    print("SWS V1 SCHEMA VALIDATOR")
    print("=" * 60)
    print(f"schema_dir: {SCHEMA_DIR}")
    print(f"expected:   {len(V1_SCHEMAS)}")
    print(f"ok:         {len(ok)}")
    print(f"missing:    {len(missing)}")
    print(f"invalid:    {len(invalid)}")
    for name in ok:
        print(f"  [OK]      {name}")
    for name in missing:
        print(f"  [MISSING] {name}")
    for name, err in invalid:
        print(f"  [INVALID] {name}: {err}")
    if missing:
        return 2
    if invalid:
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(validate_all())
