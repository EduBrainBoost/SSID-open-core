"""agents_pack — verify, list, diff and emit agent manifests (stdlib-only)."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

CANONICAL_DIR = Path(__file__).resolve().parents[2] / "24_meta_orchestration" / "agents" / "claude"
MANIFEST_NAME = "agents_manifest.json"

SUBCOMMANDS = ("verify", "list", "diff", "emit-manifest")


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _discover_agent_files(agents_dir: Path) -> dict[str, Path]:
    """Return sorted dict of agent_id -> Path for all .md files (excluding README)."""
    result: dict[str, Path] = {}
    for f in sorted(agents_dir.glob("*.md")):
        if f.name == "README.md":
            continue
        result[f.stem] = f
    return result


def load_manifest(agents_dir: Path | None = None) -> dict:
    agents_dir = agents_dir or CANONICAL_DIR
    manifest_path = agents_dir / MANIFEST_NAME
    if not manifest_path.exists():
        print(f"FAIL: manifest not found: {manifest_path}", file=sys.stderr)
        sys.exit(1)
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def verify(agents_dir: Path | None = None) -> bool:
    """Verify manifest SHA256 hashes against filesystem."""
    agents_dir = agents_dir or CANONICAL_DIR
    if not agents_dir.exists():
        print(f"SKIP: agents dir not found: {agents_dir}")
        return True

    manifest = load_manifest(agents_dir)
    errors: list[str] = []

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


def list_agents(agents_dir: Path | None = None) -> list[dict]:
    """List all agents registered in the manifest."""
    agents_dir = agents_dir or CANONICAL_DIR
    manifest = load_manifest(agents_dir)
    agents = manifest["agents"]
    for entry in agents:
        print(f"  {entry['agent_id']:40s} {entry['sha256'][:12]}... {entry['bytes']:>6d}B")
    print(f"Total: {len(agents)} agents")
    return agents


def diff(agents_dir: Path | None = None) -> dict:
    """Show drift between manifest and filesystem.

    Returns a dict with keys: added, removed, modified (each a list of agent_ids).
    """
    agents_dir = agents_dir or CANONICAL_DIR
    if not agents_dir.exists():
        print(f"SKIP: agents dir not found: {agents_dir}")
        return {"added": [], "removed": [], "modified": []}

    manifest = load_manifest(agents_dir)
    manifest_map: dict[str, dict] = {e["agent_id"]: e for e in manifest["agents"]}
    fs_map = _discover_agent_files(agents_dir)

    manifest_ids = set(manifest_map.keys())
    fs_ids = set(fs_map.keys())

    added = sorted(fs_ids - manifest_ids)
    removed = sorted(manifest_ids - fs_ids)
    modified: list[str] = []

    for agent_id in sorted(manifest_ids & fs_ids):
        actual_hash = _hash_file(fs_map[agent_id])
        if actual_hash != manifest_map[agent_id]["sha256"]:
            modified.append(agent_id)

    result = {"added": added, "removed": removed, "modified": modified}

    if added:
        print("Added (on disk, not in manifest):")
        for a in added:
            print(f"  + {a}")
    if removed:
        print("Removed (in manifest, not on disk):")
        for r in removed:
            print(f"  - {r}")
    if modified:
        print("Modified (SHA256 mismatch):")
        for m in modified:
            print(f"  ~ {m}")
    if not added and not removed and not modified:
        print("No drift detected.")

    return result


def emit_manifest(agents_dir: Path | None = None) -> dict:
    """Generate manifest from filesystem and write agents_manifest.json."""
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
    if len(sys.argv) < 2 or sys.argv[1] not in SUBCOMMANDS:
        print(f"Usage: python agents_pack.py {{{','.join(SUBCOMMANDS)}}} [agents_dir]")
        return 1

    agents_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    cmd = sys.argv[1]

    if cmd == "verify":
        return 0 if verify(agents_dir) else 1
    elif cmd == "list":
        list_agents(agents_dir)
        return 0
    elif cmd == "diff":
        result = diff(agents_dir)
        return 1 if (result["added"] or result["removed"] or result["modified"]) else 0
    elif cmd == "emit-manifest":
        emit_manifest(agents_dir)
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
