#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
from pathlib import Path


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _warn(msg: str) -> None:
    print(f"WARN: {msg}", file=sys.stderr)


def _repo_root() -> Path:
    # .../<repo>/23_compliance/scripts/build_entities_list.py
    return Path(__file__).resolve().parents[2]


def _resolve_source(repo_root: Path) -> Path | None:
    env = os.environ.get("SANCTIONS_SOURCE", "").strip()
    if env:
        p = Path(env)
        if not p.is_absolute():
            p = (repo_root / p).resolve()
        return p if p.exists() and p.is_file() else None

    # conservative defaults (no broad globbing)
    candidates = [
        repo_root / "23_compliance" / "data" / "sanctions" / "entities_source.json",
        repo_root / "23_compliance" / "data" / "sanctions" / "entities.csv",
        repo_root / "23_compliance" / "data" / "sanctions" / "entities.txt",
        repo_root / "23_compliance" / "data" / "sanctions" / "entities.json",
    ]
    for c in candidates:
        if c.exists() and c.is_file():
            return c
    return None


def _resolve_output(repo_root: Path) -> Path | None:
    env = os.environ.get("SANCTIONS_OUTPUT", "").strip()
    if env:
        p = Path(env)
        if not p.is_absolute():
            p = (repo_root / p).resolve()
        return p

    # prefer existing output (avoid creating new compliance artifacts silently)
    candidates = [
        repo_root / "23_compliance" / "data" / "sanctions" / "entities_list.json",
        repo_root / "23_compliance" / "data" / "entities_list.json",
    ]
    for c in candidates:
        if c.exists() and c.is_file():
            return c

    # if none exists: only create when explicitly allowed
    allow_create = os.environ.get("SANCTIONS_ALLOW_CREATE_OUTPUT", "").strip() == "1"
    if allow_create:
        return candidates[0]
    return None


def _extract_entities_from_json(obj) -> list[str]:
    # accept: list[str] | list[dict{name|entity}] | dict{entities:[...]}
    if isinstance(obj, dict):
        obj = obj.get("entities", [])
    if not isinstance(obj, list):
        raise ValueError("JSON source must be a list or dict with 'entities' list")

    out: list[str] = []
    for item in obj:
        if isinstance(item, str):
            s = item.strip()
            if s:
                out.append(s)
        elif isinstance(item, dict):
            for k in ("name", "entity", "value"):
                v = item.get(k)
                if isinstance(v, str) and v.strip():
                    out.append(v.strip())
                    break
    return out


def _extract_entities(src: Path) -> tuple[list[str], str]:
    b = src.read_bytes()
    src_hash = _sha256_bytes(b)

    if src.suffix.lower() == ".json":
        obj = json.loads(b.decode("utf-8"))
        ents = _extract_entities_from_json(obj)
        return ents, src_hash

    if src.suffix.lower() == ".csv":
        text = b.decode("utf-8", errors="strict")
        r = csv.reader(text.splitlines())
        ents: list[str] = []
        for row in r:
            if not row:
                continue
            s = str(row[0]).strip()
            if s and not s.lower().startswith("name"):
                ents.append(s)
        return ents, src_hash

    if src.suffix.lower() == ".txt":
        text = b.decode("utf-8", errors="strict")
        ents = []
        for line in text.splitlines():
            s = line.strip()
            if s and not s.startswith("#"):
                ents.append(s)
        return ents, src_hash

    raise ValueError(f"Unsupported source format: {src.suffix}")


def _write_output(out_path: Path, entities: list[str], source_path: str, source_sha: str) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # stable, deterministic list
    ents = sorted(set(entities))

    if out_path.exists():
        try:
            existing = json.loads(out_path.read_text(encoding="utf-8"))
        except Exception:
            existing = None

        # preserve output shape if possible
        if isinstance(existing, list):
            out_path.write_text(json.dumps(ents, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            return

        if isinstance(existing, dict):
            existing["source_path"] = source_path
            existing["source_sha256"] = source_sha
            existing["entities"] = ents
            out_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            return

    # create dict output only when output path is explicitly allowed/exists
    payload = {"source_path": source_path, "source_sha256": source_sha, "entities": ents}
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    repo_root = _repo_root()
    src = _resolve_source(repo_root)
    outp = _resolve_output(repo_root)

    if not src:
        _warn("sanctions source missing; skipping (exit 0). Set SANCTIONS_SOURCE to enable.")
        return 0

    try:
        entities, src_sha = _extract_entities(src)
    except Exception as e:
        _warn(f"sanctions source exists but cannot be parsed: {e}")
        return 2

    if not outp:
        _warn(
            "no output path (no existing entities_list.json). Skipping write. Set SANCTIONS_OUTPUT or SANCTIONS_ALLOW_CREATE_OUTPUT=1."
        )
        return 0

    _write_output(outp, entities, str(src), src_sha)
    print(f"OK: wrote {outp} (entities={len(set(entities))})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
