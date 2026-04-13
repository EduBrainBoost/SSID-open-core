import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class EvidenceEntry:
    check: str
    result: str
    file_path: str | None = None
    sha256: str | None = None
    findings: int = 0
    details: dict | None = None

    def to_jsonl(self) -> str:
        d = asdict(self)
        d["ts"] = datetime.now(UTC).isoformat()
        return json.dumps({k: v for k, v in d.items() if v is not None})


class EvidenceWriter:
    def __init__(self, run_id: str, out_dir: Path):
        self.run_id = run_id
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self._evidence_path = self.out_dir / "evidence.jsonl"
        self._entry_count = 0

    def append(self, entry: EvidenceEntry) -> None:
        with open(self._evidence_path, "a", encoding="utf-8") as f:
            f.write(entry.to_jsonl() + "\n")
        self._entry_count += 1

    def finalize(self, status: str, autorunner_id: str, gates_passed: list = None, gates_failed: list = None) -> dict:
        evidence_sha = ""
        if self._evidence_path.exists():
            evidence_sha = hashlib.sha256(self._evidence_path.read_bytes()).hexdigest()

        manifest = {
            "run_id": self.run_id,
            "autorunner_id": autorunner_id,
            "status": status,
            "ts_end": datetime.now(UTC).isoformat(),
            "gates_passed": gates_passed or [],
            "gates_failed": gates_failed or [],
            "sha256_of_evidence": evidence_sha,
            "agent_used": False,
            "evidence_lines": self._entry_count,
        }

        manifest_path = self.out_dir / "manifest.json"
        if manifest_path.exists():
            raise FileExistsError(
                f"WORM violation: manifest already exists at {manifest_path}. "
                "finalize() must only be called once per EvidenceWriter."
            )
        manifest_bytes = json.dumps(manifest, indent=2).encode()
        manifest_path.write_bytes(manifest_bytes)
        (self.out_dir / "manifest.json.sha256").write_text(hashlib.sha256(manifest_bytes).hexdigest())
        return manifest
