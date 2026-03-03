"""
cron_sha256_manifest.py - T-021 Evidence SHA256 Manifest Writer
Writes SHA256 manifest for cron job outputs to WORM storage.
"""
import json, hashlib, sys
from datetime import datetime, timezone
from pathlib import Path

def write_manifest(job_id: str, output_files: list, repo_root: str = ".") -> dict:
    root = Path(repo_root)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    worm_dir = root / "02_audit_logging" / "storage" / "worm" / job_id / ts
    worm_dir.mkdir(parents=True, exist_ok=True)

    manifest = {"run_ts": ts, "job_id": job_id, "files": []}
    for f in output_files:
        p = Path(f)
        if p.exists():
            sha = hashlib.sha256(p.read_bytes()).hexdigest()
            manifest["files"].append({"path": str(p), "sha256": sha})

    manifest_path = worm_dir / "sha256_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))

    log_path = root / "02_audit_logging" / "logs" / "cron_runs.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a") as f:
        f.write(json.dumps({"ts": ts, "job": job_id, "manifest": str(manifest_path)}) + "\n")

    return manifest

if __name__ == "__main__":
    job = sys.argv[1] if len(sys.argv) > 1 else "unknown"
    files = sys.argv[2:] if len(sys.argv) > 2 else []
    result = write_manifest(job, files)
    print(json.dumps(result, indent=2))
