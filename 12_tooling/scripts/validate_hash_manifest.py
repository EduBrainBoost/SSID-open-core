#!/usr/bin/env python3
import hashlib
import json
import os
from pathlib import Path

_SSID_ROOT = Path(os.environ.get("SSID_PATH", str(Path(__file__).resolve().parents[2])))
BUNDLE = _SSID_ROOT / "02_audit_logging" / "evidence" / "tasks" / "manual_backfill_20260213T090000Z"


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().lower()


# Load manifest
manifest = json.loads((BUNDLE / "RELEASE_AUDIT_hash_manifest.json").read_text(encoding="utf-8-sig"))
files_in_manifest = manifest.get("files", [])

print("Validating Hash Manifest:")
print("=" * 80)

all_match = True
for entry in files_in_manifest:
    rel_path = entry.get("path")
    expected_sha = entry.get("sha256", "").lower()

    if not rel_path or not expected_sha:
        print(f"❌ BAD_ENTRY: {entry}")
        all_match = False
        continue

    file_path = BUNDLE / rel_path
    if not file_path.exists():
        print(f"❌ FILE_NOT_FOUND: {rel_path}")
        all_match = False
        continue

    actual_sha = sha256_file(file_path)
    actual_size = file_path.stat().st_size

    match = "✅" if actual_sha == expected_sha else "❌"
    print(f"{match} {rel_path}")
    print(f"   Expected: {expected_sha}")
    print(f"   Actual:   {actual_sha}")
    print(f"   Size:     {actual_size} bytes (manifest: {entry.get('bytes')})")

    if actual_sha != expected_sha:
        all_match = False

print("=" * 80)
print("HASH_MANIFEST_MATCH" if all_match else "HASH_MANIFEST_MISMATCH")
