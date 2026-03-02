#!/usr/bin/env python3
"""Build a deterministic ZIP bundle from public_export/ with SHA256SUMS.

Determinism guarantees:
- Files sorted lexicographically
- Timestamps fixed to SOURCE_DATE_EPOCH (or 2026-01-01T00:00:00Z)
- Compression level fixed (ZIP_DEFLATED, compresslevel=9)
- No OS-specific metadata
"""

import argparse
import hashlib
import os
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path


SOURCE_DATE_EPOCH = int(os.environ.get("SOURCE_DATE_EPOCH", "1767225600"))
FIXED_DATE = (2026, 1, 1, 0, 0, 0)

DENY_PATTERNS = [
    ".env", ".secret", ".token", ".pem", ".key", ".p12", ".pfx",
    "__pycache__", ".pyc", ".git", ".DS_Store", "Thumbs.db",
    "node_modules",
]


def is_denied(path: Path) -> bool:
    """Check if a path matches any deny pattern."""
    parts = path.parts + (path.name,)
    for part in parts:
        for pattern in DENY_PATTERNS:
            if part == pattern or part.endswith(pattern):
                return True
    return False


def sha256_file(filepath: Path) -> str:
    """Compute SHA256 of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    """Compute SHA256 of bytes."""
    return hashlib.sha256(data).hexdigest()


def build_bundle(source_dir: Path, output_dir: Path) -> tuple[Path, Path]:
    """Build deterministic ZIP and SHA256SUMS.

    Returns (zip_path, sha256sums_path).
    """
    if not source_dir.is_dir():
        print(f"ERROR: source directory not found: {source_dir}", file=sys.stderr)
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Collect files, sorted, deny-filtered
    files: list[Path] = []
    for f in sorted(source_dir.rglob("*")):
        if f.is_file() and not is_denied(f.relative_to(source_dir)):
            files.append(f)

    if not files:
        print(f"ERROR: no files found in {source_dir}", file=sys.stderr)
        sys.exit(1)

    # Determine bundle name
    timestamp = datetime.fromtimestamp(SOURCE_DATE_EPOCH, tz=timezone.utc).strftime("%Y%m%d")
    zip_name = f"ssid-open-core-{timestamp}.zip"
    zip_path = output_dir / zip_name
    sha256sums_path = output_dir / "SHA256SUMS"

    # Build ZIP deterministically
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for filepath in files:
            arcname = str(filepath.relative_to(source_dir))
            data = filepath.read_bytes()
            info = zipfile.ZipInfo(filename=arcname, date_time=FIXED_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, data)

    # SHA256SUMS
    zip_hash = sha256_file(zip_path)
    lines = [f"{zip_hash}  {zip_name}"]

    # Also hash individual source files for auditability
    for filepath in files:
        rel = filepath.relative_to(source_dir).as_posix()
        file_hash = sha256_file(filepath)
        lines.append(f"{file_hash}  source/{rel}")

    sha256sums_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Bundle: {zip_path} ({len(files)} files)")
    print(f"SHA256: {zip_hash}")
    print(f"Sums:   {sha256sums_path}")

    return zip_path, sha256sums_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build deterministic release bundle")
    parser.add_argument("--source-dir", required=True, help="Source directory (public_export/)")
    parser.add_argument("--output-dir", required=True, help="Output directory for ZIP + SHA256SUMS")
    args = parser.parse_args()

    build_bundle(Path(args.source_dir), Path(args.output_dir))


if __name__ == "__main__":
    main()
