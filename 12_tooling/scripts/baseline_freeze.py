#!/usr/bin/env python3
"""Baseline Freeze: Captures SHA256 hashes of all tracked files."""
from __future__ import annotations
import argparse, hashlib, json, subprocess, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
DEFAULT_OUT = REPO / "24_meta_orchestration" / "registry" / "manifests" / "baseline_freeze.json"
def _sha256(p):
    try: return hashlib.sha256(p.read_bytes()).hexdigest()
    except: return "ERROR_READ"
def _tracked():
    r = subprocess.run(["git","ls-files"], capture_output=True, text=True, cwd=str(REPO))
    return sorted(f.strip() for f in r.stdout.splitlines() if f.strip())
def freeze(out):
    m = {}
    for f in _tracked():
        fp = REPO / f
        if fp.is_file(): m[f] = _sha256(fp)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"version":"1.0","file_count":len(m),"hashes":m}, indent=2), encoding="utf-8")
    print(f"Baseline frozen: {len(m)} files -> {out}"); return m
def verify(bp):
    if not bp.exists(): print(f"FAIL: not found: {bp}", file=sys.stderr); return 24
    data = json.loads(bp.read_text(encoding="utf-8"))
    drift = []
    for f, h in data.get("hashes",{}).items():
        fp = REPO / f
        if not fp.exists(): drift.append((f,"MISSING"))
        elif _sha256(fp) != h: drift.append((f,"CHANGED"))
    if drift:
        print(f"FAIL: {len(drift)} files drifted", file=sys.stderr)
        for p,s in drift[:10]: print(f"  {s}: {p}", file=sys.stderr)
        return 24
    print(f"PASS: baseline verified"); return 0
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()
    if args.verify: return verify(args.output)
    freeze(args.output); return 0
if __name__ == "__main__": raise SystemExit(main())
