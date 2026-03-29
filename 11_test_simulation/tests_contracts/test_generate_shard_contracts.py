from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_generate_shard_contracts_creates_expected_files(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    bootstrap = repo_root / "12_tooling" / "cli" / "chart_manifest_bootstrap.py"
    generator = repo_root / "12_tooling" / "cli" / "generate_shard_contracts.py"

    subprocess.run(["python", str(bootstrap), "--repo-root", str(tmp_path)], check=True, cwd=str(repo_root))
    result = subprocess.run(["python", str(generator), "--repo-root", str(tmp_path)], check=True, cwd=str(repo_root), capture_output=True, text=True)
    payload = json.loads(result.stdout)

    target_dir = tmp_path / "20_foundation" / "shards" / "10_finanzen_banking" / "contracts"
    assert (target_dir / "inputs.schema.json").exists()
    assert (target_dir / "outputs.schema.json").exists()
    assert (target_dir / "events.schema.json").exists()
    assert payload["contracts_created"] >= 0
