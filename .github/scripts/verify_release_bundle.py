#!/usr/bin/env python3
"""Verify a release bundle: extract ZIP, compare SHA256 sums.

Exit 0 = PASS, Exit 1 = FAIL.
"""

import argparse
import hashlib
import sys
import tempfile
import zipfile
from pathlib import Path


def sha256_file(filepath: Path) -> str:
    """Compute SHA256 of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_bundle(zip_path: Path, sha256sums_path: Path) -> bool:
    """Verify ZIP integrity against SHA256SUMS.

    Returns True if all checks pass.
    """
    if not zip_path.exists():
        print(f"FAIL: ZIP not found: {zip_path}", file=sys.stderr)
        return False

    if not sha256sums_path.exists():
        print(f"FAIL: SHA256SUMS not found: {sha256sums_path}", file=sys.stderr)
        return False

    # Parse SHA256SUMS
    sums: dict[str, str] = {}
    for line in sha256sums_path.read_text(encoding="utf-8").strip().splitlines():
        if not line.strip():
            continue
        parts = line.split("  ", 1)
        if len(parts) != 2:
            print(f"FAIL: malformed SHA256SUMS line: {line}", file=sys.stderr)
            return False
        sums[parts[1].strip()] = parts[0].strip()

    # Verify ZIP hash
    zip_name = zip_path.name
    if zip_name not in sums:
        print(f"FAIL: ZIP {zip_name} not found in SHA256SUMS", file=sys.stderr)
        return False

    actual_hash = sha256_file(zip_path)
    expected_hash = sums[zip_name]
    if actual_hash != expected_hash:
        print(f"FAIL: ZIP hash mismatch", file=sys.stderr)
        print(f"  expected: {expected_hash}", file=sys.stderr)
        print(f"  actual:   {actual_hash}", file=sys.stderr)
        return False

    print(f"PASS: ZIP hash matches ({zip_name})")

    # Extract and verify individual files
    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmpdir)

        source_entries = {k: v for k, v in sums.items() if k.startswith("source/")}
        failures = 0

        for entry_name, expected in source_entries.items():
            rel_path = entry_name.removeprefix("source/")
            extracted = Path(tmpdir) / rel_path

            if not extracted.exists():
                print(f"FAIL: {rel_path} missing from ZIP", file=sys.stderr)
                failures += 1
                continue

            actual = sha256_file(extracted)
            if actual != expected:
                print(f"FAIL: {rel_path} hash mismatch", file=sys.stderr)
                print(f"  expected: {expected}", file=sys.stderr)
                print(f"  actual:   {actual}", file=sys.stderr)
                failures += 1
            else:
                print(f"PASS: {rel_path}")

    if failures > 0:
        print(f"\nFAIL: {failures} file(s) failed verification", file=sys.stderr)
        return False

    print(f"\nPASS: all checks passed")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify release bundle integrity")
    parser.add_argument("--zip", required=True, help="Path to ZIP file")
    parser.add_argument("--sha256sums", required=True, help="Path to SHA256SUMS file")
    args = parser.parse_args()

    ok = verify_bundle(Path(args.zip), Path(args.sha256sums))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
