"""agents_pack — verify and emit agent manifests (stdlib-only)."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

CANONICAL_DIR = Path(__file__).resolve().parents[2] / "24_meta_orchestration" / "agents" / "claude"
MANIFEST_NAME = "agents_manifest.json"


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_manifest(agents_dir: Path | None = None) -> dict:
    agents_dir = agents_dir or CANONICAL_DIR
    manifest_path = agents_dir / MANIFEST_NAME
    if not manifest_path.exists():
        print(f"FAIL: manifest not found: {manifest_path}", file=sys.stderr)
        sys.exit(1)
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def verify(agents_dir: Path | None = None) -> bool:
    agents_dir = agents_dir or CANONICAL_DIR
    if not agents_dir.exists():
        print(f"SKIP: agents dir not found: {agents_dir}")
        return True

    manifest = load_manifest(agents_dir)
    errors = []

    for entry in manifest["agents"]:
        fpath = agents_dir / entry["filename"]
        if not fpath.exists():
            errors.append(f"MISSING: {entry['filename']}")
            continue
        actual_hash = _hash_file(fpath)
        if actual_hash != entry["sha256"]:
            errors.append(
                f"MISMATCH: {entry['filename']} "
                f"expected={entry['sha256'][:12]}... "
                f"actual={actual_hash[:12]}..."
            )

    if errors:
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        print(f"FAIL: {len(errors)} error(s)")
        return False

    print(f"PASS: {len(manifest['agents'])} agents verified")
    return True


def emit_manifest(agents_dir: Path | None = None) -> dict:
    agents_dir = agents_dir or CANONICAL_DIR
    agents = []
    for f in sorted(agents_dir.glob("*.md")):
        if f.name == "README.md":
            continue
        data = f.read_bytes()
        agents.append(
            {
                "agent_id": f.stem,
                "filename": f.name,
                "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
                "lines": data.count(b"\n"),
            }
        )

    manifest = {"version": 1, "agents": agents}
    manifest_path = agents_dir / MANIFEST_NAME
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {manifest_path} ({len(agents)} agents)")
    return manifest


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in ("verify", "emit-manifest"):
        print("Usage: python agents_pack.py {verify|emit-manifest} [agents_dir]")
        return 1

    agents_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else None

    if sys.argv[1] == "verify":
        return 0 if verify(agents_dir) else 1
    elif sys.argv[1] == "emit-manifest":
        emit_manifest(agents_dir)
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
