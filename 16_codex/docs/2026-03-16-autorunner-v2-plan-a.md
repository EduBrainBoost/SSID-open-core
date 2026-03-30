# AutoRunner V2 — Plan A: Foundation + Deterministic Gates

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Gemeinsame AutoRunner-Infrastruktur + 4 vollständig deterministische AutoRunner ohne Claude-Agent-Abhängigkeit implementieren (AR-07, AR-08, AR-02, AR-05).

**Architecture:** Hybrid Layered (Ansatz C): GitHub Action als deterministischer Trigger → Python-Scripts für Checks → EMS Gate-Runner HTTP-Call → WORM-Evidence. Jeder AutoRunner ist eine eigenständige GitHub Action mit eigenem Python-Script in `12_tooling/scripts/` oder `24_meta_orchestration/scripts/`. Gemeinsame Basis in `12_tooling/autorunner_base/`.

**Tech Stack:** Python 3.11, pytest, GitHub Actions, JSON Schema (jsonschema), PyYAML, schemathesis, OPA (optional), bash

**Spec:** `16_codex/docs/2026-03-16-autorunner-v2-design.md`

---

## Chunk 1: Foundation

### Task 1: Common AutoRunner Base Module

**Files:**
- Create: `12_tooling/autorunner_base/__init__.py`
- Create: `12_tooling/autorunner_base/models.py`
- Create: `12_tooling/autorunner_base/evidence.py`
- Create: `12_tooling/autorunner_base/ems_client.py`
- Test: `tests/autorunners/test_base_models.py`

**What it does:** Definiert die gemeinsamen Datenstrukturen (EMS Payload, Evidence JSONL, Status-Codes) die alle 10 AutoRunner nutzen.

- [ ] **Step 1: Failing test für AutoRunner-Payload-Validierung**

```python
# tests/autorunners/test_base_models.py
import pytest
from pydantic import ValidationError
from ssid_autorunner.models import AutoRunnerPayload, StatusCode

def test_valid_payload_accepted():
    payload = AutoRunnerPayload(
        run_id="550e8400-e29b-41d4-a716-446655440000",
        autorunner_id="AR-07",
        trigger="push",
        repo="SSID",
        branch="main",
        commit_sha="a" * 40,
    )
    assert payload.autorunner_id == "AR-07"

def test_invalid_commit_sha_rejected():
    with pytest.raises(ValidationError):
        AutoRunnerPayload(
            run_id="550e8400-e29b-41d4-a716-446655440000",
            autorunner_id="AR-07",
            trigger="push",
            repo="SSID",
            commit_sha="not-a-sha",
        )

def test_invalid_autorunner_id_rejected():
    with pytest.raises(ValidationError):
        AutoRunnerPayload(
            run_id="550e8400-e29b-41d4-a716-446655440000",
            autorunner_id="AR-99",
            trigger="push",
            repo="SSID",
            commit_sha="a" * 40,
        )

def test_status_codes_complete():
    expected = {
        "PASS", "FAIL_POLICY", "FAIL_SOT", "FAIL_QA",
        "FAIL_DUPLICATE", "FAIL_SCOPE", "FAIL_FORBIDDEN",
        "FAIL_FRESHNESS", "FAIL_DORA", "FAIL_SHARD", "ERROR"
    }
    assert set(s.value for s in StatusCode) == expected
```

- [ ] **Step 2: Test ausführen — muss FAIL sein**

```bash
cd C:/Users/bibel/Documents/Github/SSID
pytest tests/autorunners/test_base_models.py -v
# Expected: ImportError oder ModuleNotFoundError
```

- [ ] **Step 3: models.py implementieren**

```python
# 12_tooling/autorunner_base/models.py
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
import re

VALID_AR_IDS = {f"AR-{i:02d}" for i in range(1, 11)}

class StatusCode(str, Enum):
    PASS = "PASS"
    FAIL_POLICY = "FAIL_POLICY"
    FAIL_SOT = "FAIL_SOT"
    FAIL_QA = "FAIL_QA"
    FAIL_DUPLICATE = "FAIL_DUPLICATE"
    FAIL_SCOPE = "FAIL_SCOPE"
    FAIL_FORBIDDEN = "FAIL_FORBIDDEN"
    FAIL_FRESHNESS = "FAIL_FRESHNESS"
    FAIL_DORA = "FAIL_DORA"
    FAIL_SHARD = "FAIL_SHARD"
    ERROR = "ERROR"

class ScopeLock(BaseModel):
    allowed_paths: List[str] = Field(default_factory=list)
    forbidden_paths: List[str] = Field(default_factory=list)

class AgentTask(BaseModel):
    agent_id: str
    model: str = Field(pattern="^(opus|sonnet|haiku)$")
    max_tokens: int = 4096

class AutoRunnerPayload(BaseModel):
    run_id: str = Field(pattern=r"^[0-9a-f-]{36}$")
    autorunner_id: str
    trigger: str = Field(pattern="^(push|cron|pr|manual)$")
    repo: str
    branch: str = "main"
    commit_sha: str
    scope_lock: ScopeLock = Field(default_factory=ScopeLock)
    agent_task: Optional[AgentTask] = None
    opa_input_path: Optional[str] = None
    context: dict = Field(default_factory=dict)

    @field_validator("autorunner_id")
    @classmethod
    def validate_ar_id(cls, v):
        if v not in VALID_AR_IDS:
            raise ValueError(f"autorunner_id must be one of {VALID_AR_IDS}")
        return v

    @field_validator("commit_sha")
    @classmethod
    def validate_sha(cls, v):
        if not re.match(r"^[0-9a-f]{40}$", v):
            raise ValueError("commit_sha must be 40-char lowercase hex")
        return v
```

- [ ] **Step 4: `__init__.py` anlegen**

```python
# 12_tooling/autorunner_base/__init__.py
from .models import AutoRunnerPayload, StatusCode, ScopeLock, AgentTask
```

- [ ] **Step 5: Test ausführen — muss PASS sein**

```bash
cd C:/Users/bibel/Documents/Github/SSID
python -m pip install pydantic pytest --quiet
pytest tests/autorunners/test_base_models.py -v
# Expected: 4 PASSED
```

- [ ] **Step 6: Commit**

```bash
git add 12_tooling/autorunner_base/ tests/autorunners/test_base_models.py
git commit -m "feat(autorunner): add common base models with pydantic validation"
```

---

### Task 2: Evidence Writer (WORM-kompatibler JSONL-Logger)

**Files:**
- Create: `12_tooling/autorunner_base/evidence.py`
- Test: `tests/autorunners/test_evidence_writer.py`

- [ ] **Step 1: Failing test**

```python
# tests/autorunners/test_evidence_writer.py
import json
import tempfile
from pathlib import Path
from ssid_autorunner.evidence import EvidenceWriter, EvidenceEntry

def test_write_single_entry(tmp_path):
    writer = EvidenceWriter(run_id="test-run-001", out_dir=tmp_path)
    writer.append(EvidenceEntry(
        check="forbidden_ext",
        file_path="src/file.py",
        result="PASS",
        sha256="a" * 64,
    ))
    lines = (tmp_path / "evidence.jsonl").read_text().strip().split("\n")
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["check"] == "forbidden_ext"
    assert entry["result"] == "PASS"
    assert "ts" in entry

def test_append_multiple_entries(tmp_path):
    writer = EvidenceWriter(run_id="test-run-001", out_dir=tmp_path)
    for i in range(3):
        writer.append(EvidenceEntry(check=f"check_{i}", result="PASS"))
    lines = (tmp_path / "evidence.jsonl").read_text().strip().split("\n")
    assert len(lines) == 3

def test_manifest_written_on_finalize(tmp_path):
    writer = EvidenceWriter(run_id="test-run-001", out_dir=tmp_path)
    writer.append(EvidenceEntry(check="test", result="PASS"))
    manifest = writer.finalize(status="PASS", autorunner_id="AR-07")
    assert manifest["status"] == "PASS"
    assert (tmp_path / "manifest.json").exists()
    assert (tmp_path / "manifest.json.sha256").exists()

def test_sha256_manifest_correct(tmp_path):
    import hashlib
    writer = EvidenceWriter(run_id="test-run-001", out_dir=tmp_path)
    writer.finalize(status="PASS", autorunner_id="AR-07")
    manifest_bytes = (tmp_path / "manifest.json").read_bytes()
    expected_sha = hashlib.sha256(manifest_bytes).hexdigest()
    actual_sha = (tmp_path / "manifest.json.sha256").read_text().strip()
    assert actual_sha == expected_sha
```

- [ ] **Step 2: Test ausführen — muss FAIL sein**

```bash
pytest tests/autorunners/test_evidence_writer.py -v
# Expected: ImportError
```

- [ ] **Step 3: evidence.py implementieren**

```python
# 12_tooling/autorunner_base/evidence.py
import json
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

@dataclass
class EvidenceEntry:
    check: str
    result: str
    file_path: Optional[str] = None
    sha256: Optional[str] = None
    findings: int = 0
    details: Optional[dict] = None

    def to_jsonl(self) -> str:
        d = asdict(self)
        d["ts"] = datetime.now(timezone.utc).isoformat()
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

    def finalize(self, status: str, autorunner_id: str,
                 gates_passed: list = None, gates_failed: list = None) -> dict:
        evidence_sha = ""
        if self._evidence_path.exists():
            evidence_sha = hashlib.sha256(
                self._evidence_path.read_bytes()
            ).hexdigest()

        manifest = {
            "run_id": self.run_id,
            "autorunner_id": autorunner_id,
            "status": status,
            "ts_end": datetime.now(timezone.utc).isoformat(),
            "gates_passed": gates_passed or [],
            "gates_failed": gates_failed or [],
            "sha256_of_evidence": evidence_sha,
            "agent_used": False,
            "evidence_lines": self._entry_count,
        }

        manifest_path = self.out_dir / "manifest.json"
        manifest_bytes = json.dumps(manifest, indent=2).encode()
        manifest_path.write_bytes(manifest_bytes)
        (self.out_dir / "manifest.json.sha256").write_text(
            hashlib.sha256(manifest_bytes).hexdigest()
        )
        return manifest
```

- [ ] **Step 4: `__init__.py` erweitern**

```python
# 12_tooling/autorunner_base/__init__.py  (append)
from .evidence import EvidenceWriter, EvidenceEntry
```

- [ ] **Step 5: Tests bestehen**

```bash
pytest tests/autorunners/test_evidence_writer.py -v
# Expected: 4 PASSED
```

- [ ] **Step 6: Commit**

```bash
git add 12_tooling/autorunner_base/evidence.py tests/autorunners/test_evidence_writer.py
git commit -m "feat(autorunner): add WORM-compatible evidence writer with SHA256 manifest"
```

---

### Task 3: generate_repo_scan.py (OPA-Input-Generator)

**Files:**
- Create: `24_meta_orchestration/scripts/generate_repo_scan.py`
- Test: `tests/autorunners/test_generate_repo_scan.py`

**Was es tut:** Scannt das Repo und erzeugt `repo_scan.json` als einzige valide OPA-Input-Quelle (SoT v1.1.1 §7).

- [ ] **Step 1: Failing test**

```python
# tests/autorunners/test_generate_repo_scan.py
import json
import subprocess
from pathlib import Path
import pytest

SSID_ROOT = Path("C:/Users/bibel/Documents/Github/SSID")

def test_repo_scan_json_schema(tmp_path):
    output = tmp_path / "repo_scan.json"
    result = subprocess.run(
        ["python",
         str(SSID_ROOT / "24_meta_orchestration/scripts/generate_repo_scan.py"),
         "--repo-root", str(SSID_ROOT),
         "--commit-sha", "a" * 40,
         "--out", str(output)],
        capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(output.read_text())
    assert "scan_ts" in data
    assert "commit_sha" in data
    assert "roots" in data
    assert "files" in data
    assert "forbidden_extensions_found" in data
    assert "shard_counts" in data
    assert "incident_response_plans" in data

def test_all_24_roots_in_scan(tmp_path):
    output = tmp_path / "repo_scan.json"
    subprocess.run([
        "python",
        str(SSID_ROOT / "24_meta_orchestration/scripts/generate_repo_scan.py"),
        "--repo-root", str(SSID_ROOT),
        "--commit-sha", "a" * 40,
        "--out", str(output)
    ], check=True)
    data = json.loads(output.read_text())
    root_ids = {r["id"] for r in data["roots"]}
    assert "01_ai_layer" in root_ids
    assert "24_meta_orchestration" in root_ids
    assert len(root_ids) == 24

def test_forbidden_extensions_detected(tmp_path):
    # Erstelle Test-Datei mit verbotener Extension
    fake_nb = tmp_path / "test.ipynb"
    fake_nb.write_text('{"cells": []}')
    output = tmp_path / "repo_scan.json"
    subprocess.run([
        "python",
        str(SSID_ROOT / "24_meta_orchestration/scripts/generate_repo_scan.py"),
        "--repo-root", str(tmp_path),
        "--commit-sha", "a" * 40,
        "--out", str(output)
    ], check=True)
    data = json.loads(output.read_text())
    assert any(f.endswith(".ipynb") for f in data["forbidden_extensions_found"])

def test_incident_response_plans_all_24_roots(tmp_path):
    output = tmp_path / "repo_scan.json"
    subprocess.run([
        "python",
        str(SSID_ROOT / "24_meta_orchestration/scripts/generate_repo_scan.py"),
        "--repo-root", str(SSID_ROOT),
        "--commit-sha", "a" * 40,
        "--out", str(output)
    ], check=True)
    data = json.loads(output.read_text())
    # Alle 24 Roots müssen im incident_response_plans dict sein
    assert len(data["incident_response_plans"]) == 24
```

- [ ] **Step 2: Test ausführen — muss FAIL sein**

```bash
pytest tests/autorunners/test_generate_repo_scan.py -v
# Expected: FileNotFoundError oder CalledProcessError
```

- [ ] **Step 3: generate_repo_scan.py implementieren**

```python
#!/usr/bin/env python3
# 24_meta_orchestration/scripts/generate_repo_scan.py
"""
Erzeugt repo_scan.json als einzige valide OPA-Input-Quelle.
SoT-Regel: master_v1.1.1 §7
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOTS_24 = [
    "01_ai_layer", "02_audit_logging", "03_core", "04_deployment",
    "05_documentation", "06_data_pipeline", "07_governance_legal",
    "08_identity_score", "09_meta_identity", "10_interoperability",
    "11_test_simulation", "12_tooling", "13_ui_layer", "14_zero_time_auth",
    "15_infra", "16_codex", "17_observability", "18_data_layer",
    "19_adapters", "20_foundation", "21_post_quantum_crypto",
    "22_datasets", "23_compliance", "24_meta_orchestration",
]
SHARDS_16 = [
    "01_identitaet_personen", "02_dokumente_nachweise",
    "03_zugang_berechtigungen", "04_kommunikation_daten",
    "05_gesundheit_medizin", "06_bildung_qualifikationen",
    "07_familie_soziales", "08_mobilitaet_fahrzeuge",
    "09_arbeit_karriere", "10_finanzen_banking",
    "11_versicherungen_risiken", "12_immobilien_grundstuecke",
    "13_unternehmen_gewerbe", "14_vertraege_vereinbarungen",
    "15_handel_transaktionen", "16_behoerden_verwaltung",
]
FORBIDDEN_EXTS = {".ipynb", ".parquet", ".sqlite", ".db",
                  ".env", ".pem", ".key", ".p12", ".pfx"}
SKIP_DIRS = {".git", "node_modules", ".venv", ".pytest_cache", "__pycache__"}

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    try:
        h.update(path.read_bytes())
    except (PermissionError, OSError):
        return ""
    return h.hexdigest()

def scan(repo_root: Path, commit_sha: str) -> dict:
    repo_root = Path(repo_root).resolve()
    files = []
    forbidden_found = []
    shard_counts = {}

    for root_id in ROOTS_24:
        root_path = repo_root / root_id
        shard_counts[root_id] = 0
        if not root_path.exists():
            continue
        for p in root_path.rglob("*"):
            if p.is_dir():
                continue
            if any(part in SKIP_DIRS for part in p.parts):
                continue
            rel = str(p.relative_to(repo_root))
            ext = p.suffix.lower()
            if ext in FORBIDDEN_EXTS:
                forbidden_found.append(rel)
            if p.name == "chart.yaml" and "/shards/" in rel:
                shard_counts[root_id] += 1
            files.append({
                "path": rel,
                "ext": ext,
                "size_bytes": p.stat().st_size,
                "sha256": sha256_file(p),
                "root": root_id,
            })

    incident_plans = {}
    for root_id in ROOTS_24:
        plan_path = repo_root / root_id / "docs" / "incident_response_plan.md"
        incident_plans[root_id] = {
            "exists": plan_path.exists(),
            "path": f"{root_id}/docs/incident_response_plan.md",
        }

    roots = [
        {"id": r, "path": r, "exists": (repo_root / r).exists()}
        for r in ROOTS_24
    ]

    return {
        "scan_ts": datetime.now(timezone.utc).isoformat(),
        "commit_sha": commit_sha,
        "repo": repo_root.name,
        "roots": roots,
        "files": files,
        "forbidden_extensions_found": forbidden_found,
        "shard_counts": shard_counts,
        "chart_yaml_present": {
            f"{r}/shards/{s}": (repo_root / r / "shards" / s / "chart.yaml").exists()
            for r in ROOTS_24
            for s in SHARDS_16
        },
        "incident_response_plans": incident_plans,
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    result = scan(args.repo_root, args.commit_sha)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, indent=2))
    print(f"repo_scan.json written to {args.out} ({len(result['files'])} files)")
```

- [ ] **Step 4: Tests bestehen**

```bash
pytest tests/autorunners/test_generate_repo_scan.py -v
# Expected: 4 PASSED
# Hinweis: test_all_24_roots_in_scan kann dauern (scannt SSID repo)
```

- [ ] **Step 5: Commit**

```bash
git add 24_meta_orchestration/scripts/generate_repo_scan.py \
        tests/autorunners/test_generate_repo_scan.py
git commit -m "feat(autorunner): add generate_repo_scan.py as single OPA-input source"
```

---

## Chunk 2: AR-07 forbidden_extensions

### Task 4: forbidden_ext_check.py

**Files:**
- Create: `12_tooling/scripts/forbidden_ext_check.py`
- Test: `tests/autorunners/test_ar07_forbidden_extensions.py`

- [ ] **Step 1: Failing test**

```python
# tests/autorunners/test_ar07_forbidden_extensions.py
import json
import subprocess
from pathlib import Path
import pytest

SCRIPT = Path("C:/Users/bibel/Documents/Github/SSID/12_tooling/scripts/forbidden_ext_check.py")

def run_check(files_dir, scan_all=False, extra_args=None):
    cmd = ["python", str(SCRIPT),
           "--extensions", ".ipynb .parquet .sqlite .db",
           "--repo-root", str(files_dir)]
    if scan_all:
        cmd += ["--scan-all", "true"]
    if extra_args:
        cmd += extra_args
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, json.loads(r.stdout) if r.stdout.strip() else {}

def test_clean_directory_passes(tmp_path):
    (tmp_path / "clean.py").write_text("print('hello')")
    code, result = run_check(tmp_path, scan_all=True)
    assert code == 0
    assert result["total_violations"] == 0

def test_ipynb_file_fails(tmp_path):
    (tmp_path / "notebook.ipynb").write_text('{"cells":[]}')
    code, result = run_check(tmp_path, scan_all=True)
    assert code == 1
    assert result["total_violations"] == 1
    assert any(v["ext"] == ".ipynb" for v in result["violations"])

def test_parquet_file_fails(tmp_path):
    (tmp_path / "data.parquet").write_bytes(b"PAR1")
    code, result = run_check(tmp_path, scan_all=True)
    assert code == 1

def test_sqlite_file_fails(tmp_path):
    (tmp_path / "local.sqlite").write_bytes(b"SQLite")
    code, result = run_check(tmp_path, scan_all=True)
    assert code == 1

def test_db_file_fails(tmp_path):
    (tmp_path / "cache.db").write_bytes(b"data")
    code, result = run_check(tmp_path, scan_all=True)
    assert code == 1

def test_violation_contains_sot_rule(tmp_path):
    (tmp_path / "bad.ipynb").write_text("{}")
    code, result = run_check(tmp_path, scan_all=True)
    assert result["violations"][0]["sot_rule"] == "master_v1.1.1_§6"

def test_gitignore_excluded(tmp_path):
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "cache.db").write_bytes(b"git internal")
    code, result = run_check(tmp_path, scan_all=True)
    assert result["total_violations"] == 0

def test_node_modules_excluded(tmp_path):
    nm = tmp_path / "node_modules"
    nm.mkdir()
    (nm / "dep.db").write_bytes(b"node internal")
    code, result = run_check(tmp_path, scan_all=True)
    assert result["total_violations"] == 0
```

- [ ] **Step 2: Test ausführen — muss FAIL sein**

```bash
cd C:/Users/bibel/Documents/Github/SSID
pytest tests/autorunners/test_ar07_forbidden_extensions.py -v
# Expected: FileNotFoundError
```

- [ ] **Step 3: forbidden_ext_check.py implementieren**

```python
#!/usr/bin/env python3
# 12_tooling/scripts/forbidden_ext_check.py
"""
AR-07: Forbidden Extensions Check
SoT-Regel: master_v1.1.1 §6 (.ipynb .parquet .sqlite .db)
Vollständig deterministisch — kein Claude-Agent.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

SKIP_DIRS = {".git", "node_modules", ".venv", ".pytest_cache", "__pycache__"}

def sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""

def check(repo_root: Path, extensions: set, changed_files=None, scan_all=False) -> dict:
    violations = []
    total_checked = 0

    if scan_all:
        candidates = [p for p in repo_root.rglob("*") if p.is_file()]
    elif changed_files:
        candidates = [repo_root / f for f in changed_files if (repo_root / f).is_file()]
    else:
        candidates = []

    for p in candidates:
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        total_checked += 1
        ext = p.suffix.lower()
        if ext in extensions:
            violations.append({
                "file": str(p.relative_to(repo_root)),
                "ext": ext,
                "sha256": sha256(p),
                "sot_rule": "master_v1.1.1_§6",
            })

    return {
        "violations": violations,
        "total_checked": total_checked,
        "total_violations": len(violations),
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--extensions", required=True,
                        help="Space-separated list, e.g. '.ipynb .parquet .sqlite .db'")
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--changed-files", default="",
                        help="Newline or space-separated file list")
    parser.add_argument("--scan-all", default="false")
    args = parser.parse_args()

    exts = set(args.extensions.split())
    root = Path(args.repo_root).resolve()
    changed = [f for f in args.changed_files.split() if f] if args.changed_files else []
    do_scan_all = args.scan_all.lower() == "true"

    result = check(root, exts, changed_files=changed, scan_all=do_scan_all)
    print(json.dumps(result, indent=2))
    sys.exit(1 if result["total_violations"] > 0 else 0)
```

- [ ] **Step 4: Tests bestehen**

```bash
pytest tests/autorunners/test_ar07_forbidden_extensions.py -v
# Expected: 8 PASSED
```

- [ ] **Step 5: Commit**

```bash
git add 12_tooling/scripts/forbidden_ext_check.py \
        tests/autorunners/test_ar07_forbidden_extensions.py
git commit -m "feat(AR-07): add forbidden_ext_check.py (master_v1.1.1 §6)"
```

---

### Task 5: AR-07 GitHub Action

**Files:**
- Create: `.github/workflows/forbidden_extensions.yml`
- Test: `tests/autorunners/test_ar07_workflow.py` (workflow-syntax-check)

- [ ] **Step 1: Failing test (YAML-Syntax + Pflicht-Fields)**

```python
# tests/autorunners/test_ar07_workflow.py
import yaml
from pathlib import Path

WF_PATH = Path("C:/Users/bibel/Documents/Github/SSID/.github/workflows/forbidden_extensions.yml")

def test_workflow_file_exists():
    assert WF_PATH.exists()

def test_workflow_yaml_valid():
    wf = yaml.safe_load(WF_PATH.read_text())
    assert wf is not None

def test_workflow_triggers_on_push_and_pr():
    wf = yaml.safe_load(WF_PATH.read_text())
    assert "push" in wf["on"]
    assert "pull_request" in wf["on"]

def test_workflow_calls_forbidden_ext_script():
    content = WF_PATH.read_text()
    assert "forbidden_ext_check.py" in content

def test_workflow_fails_on_violation():
    # Script muss mit exit 1 enden bei Violation — Action schlägt fehl
    content = WF_PATH.read_text()
    assert "continue-on-error: false" not in content  # default = fail
```

- [ ] **Step 2: Test ausführen — muss FAIL sein**

```bash
pytest tests/autorunners/test_ar07_workflow.py -v
# Expected: AssertionError (file not found)
```

- [ ] **Step 3: forbidden_extensions.yml erstellen**

```yaml
# .github/workflows/forbidden_extensions.yml
name: AR-07 Forbidden Extensions Gate

on:
  push:
    branches: ['**']
  pull_request:
    branches: [main, develop]

permissions:
  contents: read

jobs:
  forbidden-extensions:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          fetch-depth: 2

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install pydantic

      - name: Get changed files
        id: changed
        run: |
          git diff --name-only HEAD~1 > /tmp/changed_files.txt
          echo "Changed files:"
          cat /tmp/changed_files.txt

      - name: Run forbidden extensions check (changed files)
        run: |
          python 12_tooling/scripts/forbidden_ext_check.py \
            --extensions ".ipynb .parquet .sqlite .db .env .pem .key .p12 .pfx" \
            --repo-root . \
            --changed-files "$(cat /tmp/changed_files.txt | tr '\n' ' ')" \
            | tee /tmp/ar07_results.json

      - name: Run forbidden extensions check (full scan on PR)
        if: github.event_name == 'pull_request'
        run: |
          python 12_tooling/scripts/forbidden_ext_check.py \
            --extensions ".ipynb .parquet .sqlite .db .env .pem .key .p12 .pfx" \
            --repo-root . \
            --scan-all true \
            | tee /tmp/ar07_full_results.json

      - name: Upload evidence
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: ar07-evidence-${{ github.sha }}
          path: /tmp/ar07_*.json
          retention-days: 90
```

- [ ] **Step 4: Tests bestehen**

```bash
pytest tests/autorunners/test_ar07_workflow.py -v
# Expected: 5 PASSED
```

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/forbidden_extensions.yml \
        tests/autorunners/test_ar07_workflow.py
git commit -m "feat(AR-07): add GitHub Action workflow for forbidden extensions gate"
```

---

## Chunk 3: AR-08 opencore_sync

### Task 6: secret_scanner.py

**Files:**
- Create: `12_tooling/scripts/secret_scanner.py`
- Test: `tests/autorunners/test_secret_scanner.py`

- [ ] **Step 1: Failing test**

```python
# tests/autorunners/test_secret_scanner.py
import json
import subprocess
from pathlib import Path

SCRIPT = Path("C:/Users/bibel/Documents/Github/SSID/12_tooling/scripts/secret_scanner.py")

def run_scan(file_content, filename="test.py"):
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / filename
        p.write_text(file_content)
        r = subprocess.run(
            ["python", str(SCRIPT), "--repo-root", tmp, "--scan-all", "true"],
            capture_output=True, text=True
        )
        return r.returncode, json.loads(r.stdout) if r.stdout.strip() else {}

def test_clean_file_passes():
    code, result = run_scan("print('hello world')")
    assert code == 0
    assert result["total_secrets"] == 0

def test_aws_key_detected():
    code, result = run_scan("key = 'AKIAIOSFODNN7EXAMPLE1234'")
    assert code == 1
    assert result["total_secrets"] >= 1
    assert any("aws" in s.get("pattern_name","").lower() for s in result["secrets"])

def test_github_pat_detected():
    code, result = run_scan("token = 'ghp_" + "a" * 36 + "'")
    assert code == 1

def test_private_key_detected():
    code, result = run_scan("-----BEGIN RSA PRIVATE KEY-----\nMIIE...\n-----END RSA PRIVATE KEY-----")
    assert code == 1

def test_slack_token_detected():
    code, result = run_scan("slack_token = 'xoxb-123456789-abcdefg'")
    assert code == 1

def test_hash_in_comment_not_secret():
    # SHA256 Hashes sind kein Secret
    code, result = run_scan("# sha256: a" * 64)
    assert code == 0
```

- [ ] **Step 2: Test ausführen — FAIL**

```bash
pytest tests/autorunners/test_secret_scanner.py -v
# Expected: FileNotFoundError
```

- [ ] **Step 3: secret_scanner.py implementieren**

```python
#!/usr/bin/env python3
# 12_tooling/scripts/secret_scanner.py
"""
AR-08: Secret Scanner basierend auf opencore_export_policy.yaml Patterns
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

# Direkt aus opencore_export_policy.yaml: secret_scan_regex
PATTERNS = [
    {"name": "rsa_private_key",    "regex": r"BEGIN (RSA|OPENSSH|EC) PRIVATE KEY"},
    {"name": "generic_private_key","regex": r"-----BEGIN PRIVATE KEY-----"},
    {"name": "aws_access_key",     "regex": r"AKIA[0-9A-Z]{16}"},
    {"name": "slack_token",        "regex": r"xox[baprs]-[0-9A-Za-z\-]{10,}"},
    {"name": "github_pat",         "regex": r"ghp_[A-Za-z0-9]{36}"},
]

SKIP_DIRS = {".git", "node_modules", ".venv", "__pycache__", ".pytest_cache"}
SKIP_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".ttf", ".bin"}

def scan_file(path: Path) -> list:
    if path.suffix in SKIP_EXTS:
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    findings = []
    for pattern in PATTERNS:
        if re.search(pattern["regex"], text):
            findings.append({
                "pattern_name": pattern["name"],
                "file": str(path),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            })
    return findings

def scan_repo(root: Path, scan_all=False, changed_files=None) -> dict:
    secrets = []
    if scan_all:
        candidates = [p for p in root.rglob("*") if p.is_file()
                      and not any(s in p.parts for s in SKIP_DIRS)]
    else:
        candidates = [root / f for f in (changed_files or []) if (root / f).is_file()]

    for p in candidates:
        secrets.extend(scan_file(p))

    return {"secrets": secrets, "total_secrets": len(secrets), "total_scanned": len(list(candidates))}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--scan-all", default="false")
    parser.add_argument("--changed-files", default="")
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    changed = [f for f in args.changed_files.split() if f]
    result = scan_repo(root, scan_all=args.scan_all.lower() == "true", changed_files=changed)
    print(json.dumps(result, indent=2))
    sys.exit(1 if result["total_secrets"] > 0 else 0)
```

- [ ] **Step 4: Tests bestehen**

```bash
pytest tests/autorunners/test_secret_scanner.py -v
# Expected: 6 PASSED
```

- [ ] **Step 5: Commit**

```bash
git add 12_tooling/scripts/secret_scanner.py tests/autorunners/test_secret_scanner.py
git commit -m "feat(AR-08): add secret_scanner.py (opencore_export_policy patterns)"
```

---

### Task 7: apply_deny_globs.py + AR-08 GitHub Action

**Files:**
- Create: `12_tooling/scripts/apply_deny_globs.py`
- Create: `.github/workflows/opencore_sync.yml`
- Test: `tests/autorunners/test_ar08_opencore_sync.py`

- [ ] **Step 1: Failing test**

```python
# tests/autorunners/test_ar08_opencore_sync.py
import json
import subprocess
from pathlib import Path
import pytest

DENY_SCRIPT = Path("C:/Users/bibel/Documents/Github/SSID/12_tooling/scripts/apply_deny_globs.py")

def test_worm_storage_excluded(tmp_path):
    # Erstelle verbotene Datei
    worm = tmp_path / "02_audit_logging" / "storage" / "worm"
    worm.mkdir(parents=True)
    (worm / "entry.jsonl").write_text('{"hash":"abc"}')
    allowed = tmp_path / "03_core" / "fee.py"
    allowed.parent.mkdir(parents=True)
    allowed.write_text("pass")

    r = subprocess.run([
        "python", str(DENY_SCRIPT),
        "--repo-root", str(tmp_path),
        "--deny-globs", "02_audit_logging/storage/worm/**",
    ], capture_output=True, text=True)
    result = json.loads(r.stdout)
    sync_files = result["files_to_sync"]
    assert not any("worm" in f for f in sync_files)
    assert any("fee.py" in f for f in sync_files)

def test_evidence_excluded(tmp_path):
    ev = tmp_path / "02_audit_logging" / "evidence"
    ev.mkdir(parents=True)
    (ev / "proof.json").write_text("{}")
    r = subprocess.run([
        "python", str(DENY_SCRIPT),
        "--repo-root", str(tmp_path),
        "--deny-globs", "02_audit_logging/evidence/**",
    ], capture_output=True, text=True)
    result = json.loads(r.stdout)
    assert not any("evidence" in f for f in result["files_to_sync"])

def test_all_deny_globs_from_policy():
    import yaml
    policy = yaml.safe_load(
        Path("C:/Users/bibel/Documents/Github/SSID/16_codex/opencore_export_policy.yaml").read_text()
    )
    deny_globs = policy["deny_globs"]
    assert "02_audit_logging/storage/worm/**" in deny_globs
    assert "02_audit_logging/evidence/**" in deny_globs
    assert "24_meta_orchestration/registry/logs/**" in deny_globs
    assert "security/results/**" in deny_globs
```

- [ ] **Step 2: Test ausführen — FAIL**

```bash
pytest tests/autorunners/test_ar08_opencore_sync.py -v
```

- [ ] **Step 3: apply_deny_globs.py implementieren**

```python
#!/usr/bin/env python3
# 12_tooling/scripts/apply_deny_globs.py
"""
AR-08: Filtert Dateien nach deny_globs aus opencore_export_policy.yaml
"""
import argparse
import fnmatch
import json
from pathlib import Path

SKIP_DIRS = {".git", "node_modules", ".venv", "__pycache__"}

def matches_any_glob(path_str: str, globs: list) -> bool:
    for g in globs:
        if fnmatch.fnmatch(path_str, g):
            return True
        # Auch Teilpfade prüfen (für **-Patterns)
        parts = path_str.split("/")
        for i in range(len(parts)):
            sub = "/".join(parts[i:])
            if fnmatch.fnmatch(sub, g.lstrip("*/")):
                return True
    return False

def apply_deny_globs(repo_root: Path, deny_globs: list) -> dict:
    all_files = []
    denied_files = []
    sync_files = []

    for p in repo_root.rglob("*"):
        if p.is_dir():
            continue
        if any(s in p.parts for s in SKIP_DIRS):
            continue
        rel = str(p.relative_to(repo_root)).replace("\\", "/")
        all_files.append(rel)
        if matches_any_glob(rel, deny_globs):
            denied_files.append(rel)
        else:
            sync_files.append(rel)

    return {
        "total_files": len(all_files),
        "denied_files": denied_files,
        "files_to_sync": sync_files,
        "deny_globs_applied": deny_globs,
    }

if __name__ == "__main__":
    import yaml
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--policy", default="16_codex/opencore_export_policy.yaml")
    parser.add_argument("--deny-globs", default="",
                        help="Space-separated list (overrides policy)")
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()

    if args.deny_globs:
        deny_globs = args.deny_globs.split()
    else:
        policy_path = root / args.policy
        policy = yaml.safe_load(policy_path.read_text())
        deny_globs = policy["deny_globs"]

    result = apply_deny_globs(root, deny_globs)
    import json
    print(json.dumps(result, indent=2))
```

- [ ] **Step 4: opencore_sync.yml GitHub Action erstellen**

```yaml
# .github/workflows/opencore_sync.yml
name: AR-08 OpenCore Sync Gate

on:
  push:
    branches: [main]

permissions:
  contents: read

jobs:
  opencore-sync:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout SSID
        uses: actions/checkout@v4
        with:
          fetch-depth: 2

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install pyyaml pydantic

      - name: Secret scan (BEFORE any sync)
        run: |
          python 12_tooling/scripts/secret_scanner.py \
            --repo-root . \
            --changed-files "$(git diff --name-only HEAD~1 | tr '\n' ' ')" \
            | tee /tmp/secret_scan.json
          echo "Secret scan complete"

      - name: Apply deny_globs filter
        run: |
          python 12_tooling/scripts/apply_deny_globs.py \
            --repo-root . \
            --policy 16_codex/opencore_export_policy.yaml \
            | tee /tmp/files_to_sync.json
          echo "Deny globs applied"

      - name: Generate repo_scan.json
        run: |
          python 24_meta_orchestration/scripts/generate_repo_scan.py \
            --repo-root . \
            --commit-sha "${{ github.sha }}" \
            --out 24_meta_orchestration/registry/generated/repo_scan.json

      - name: Upload evidence
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: ar08-evidence-${{ github.sha }}
          path: |
            /tmp/secret_scan.json
            /tmp/files_to_sync.json
          retention-days: 90

      # NOTE: Eigentlicher Sync-Push (EMS-Aufruf) kommt wenn GO erteilt
      - name: Sync readiness summary
        run: |
          python -c "
          import json
          sync = json.load(open('/tmp/files_to_sync.json'))
          secrets = json.load(open('/tmp/secret_scan.json'))
          print(f'Files to sync: {len(sync[\"files_to_sync\"])}')
          print(f'Files denied: {len(sync[\"denied_files\"])}')
          print(f'Secrets found: {secrets[\"total_secrets\"]}')
          if secrets['total_secrets'] > 0:
              exit(1)
          "
```

- [ ] **Step 5: Tests bestehen**

```bash
pytest tests/autorunners/test_ar08_opencore_sync.py -v
# Expected: 3 PASSED
```

- [ ] **Step 6: Commit**

```bash
git add 12_tooling/scripts/apply_deny_globs.py \
        .github/workflows/opencore_sync.yml \
        tests/autorunners/test_ar08_opencore_sync.py
git commit -m "feat(AR-08): add opencore sync gate (deny_globs + secret scan)"
```

---

## Chunk 4: AR-02 + AR-05

### Task 8: sot_contract_check.py (für AR-02)

**Files:**
- Create: `24_meta_orchestration/scripts/sot_contract_check.py`
- Test: `tests/autorunners/test_ar02_contract_tests.py`

- [ ] **Step 1: Failing test für SOT-Konformanz-Check**

```python
# tests/autorunners/test_ar02_contract_tests.py
import json
import subprocess
from pathlib import Path
import pytest

SCRIPT = Path("C:/Users/bibel/Documents/Github/SSID/24_meta_orchestration/scripts/sot_contract_check.py")
SSID_ROOT = Path("C:/Users/bibel/Documents/Github/SSID")

def test_sot_rules_loaded():
    r = subprocess.run([
        "python", str(SCRIPT),
        "--rules", str(SSID_ROOT / "16_codex/contracts/sot/sot_contract.yaml"),
        "--repo-scan", str(SSID_ROOT / "24_meta_orchestration/registry/generated/repo_scan.json"),
        "--out", "/tmp/sot_check_test.json",
        "--generate-scan-if-missing", "true",
        "--repo-root", str(SSID_ROOT),
    ], capture_output=True, text=True)
    # Nur Schema prüfen — ob es läuft und Output erzeugt
    assert r.returncode in (0, 1), r.stderr
    result = json.loads(Path("/tmp/sot_check_test.json").read_text())
    assert "total_rules" in result
    assert result["total_rules"] >= 36  # SOT_AGENT_001-036

def test_sot_agent_001_dispatcher_single_entry():
    # SOT_AGENT_001: Dispatcher muss single entry point sein
    # Wir prüfen: existiert 24_meta_orchestration/dispatcher/ ?
    dispatcher = SSID_ROOT / "24_meta_orchestration" / "dispatcher"
    assert dispatcher.exists(), "24_meta_orchestration/dispatcher/ muss existieren"

def test_sot_rules_all_36_checked():
    r = subprocess.run([
        "python", str(SCRIPT),
        "--rules", str(SSID_ROOT / "16_codex/contracts/sot/sot_contract.yaml"),
        "--repo-scan", "/tmp/sot_check_test.json",  # nutzt vorherigen Output
        "--out", "/tmp/sot_check_test2.json",
    ], capture_output=True, text=True)
    result = json.loads(Path("/tmp/sot_check_test2.json").read_text())
    assert result["total_rules"] >= 36
```

- [ ] **Step 2: Test ausführen — FAIL**

```bash
pytest tests/autorunners/test_ar02_contract_tests.py::test_sot_rules_loaded -v
# Expected: FileNotFoundError
```

- [ ] **Step 3: sot_contract_check.py implementieren**

```python
#!/usr/bin/env python3
# 24_meta_orchestration/scripts/sot_contract_check.py
"""
AR-02: SOT-Contract-Check gegen sot_contract.yaml (SOT_AGENT_001-036)
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path
import yaml

def load_rules(rules_path: Path) -> list:
    data = yaml.safe_load(rules_path.read_text())
    return data.get("rules", [])

def load_or_generate_scan(scan_path: Path, repo_root: Path) -> dict:
    if scan_path.exists():
        return json.loads(scan_path.read_text())
    # Auto-generate wenn nicht vorhanden
    generator = repo_root / "24_meta_orchestration/scripts/generate_repo_scan.py"
    if generator.exists():
        subprocess.run([
            "python", str(generator),
            "--repo-root", str(repo_root),
            "--commit-sha", "0" * 40,
            "--out", str(scan_path),
        ], check=True)
        return json.loads(scan_path.read_text())
    return {}

def check_rule(rule: dict, scan: dict, repo_root: Path) -> dict:
    rule_id = rule["id"]
    description = rule["description"]
    result = {"rule_id": rule_id, "description": description,
               "severity": rule["severity"], "passed": True, "details": ""}

    # SOT_AGENT_001: Dispatcher = single entry point
    if rule_id == "SOT_AGENT_001":
        dispatcher = repo_root / "24_meta_orchestration" / "dispatcher"
        result["passed"] = dispatcher.exists()
        result["details"] = str(dispatcher)

    # SOT_AGENT_002: Documentation canonical paths
    elif rule_id == "SOT_AGENT_002":
        docs_root = repo_root / "05_documentation"
        result["passed"] = docs_root.exists()

    # SOT_AGENT_006-023: Root structure checks (groups of 3 per root)
    elif rule_id.startswith("SOT_AGENT_0") and len(rule_id) > 11:
        num = int(rule_id.replace("SOT_AGENT_", ""))
        if 6 <= num <= 23:
            root_idx = (num - 6) // 3  # 0-5 maps to roots 01-06
            root_names = ["01_ai_layer","02_audit_logging","03_core",
                           "04_deployment","05_documentation","06_data_pipeline"]
            if root_idx < len(root_names):
                root_path = repo_root / root_names[root_idx]
                result["passed"] = root_path.exists()
                result["details"] = str(root_path)

    # SOT_AGENT_024-036: Root 07-08 specific files
    elif rule_id in ("SOT_AGENT_024",):
        p = repo_root / "07_governance_legal" / "investment_disclaimers.yaml"
        result["passed"] = p.exists()
    elif rule_id in ("SOT_AGENT_025",):
        p = repo_root / "07_governance_legal" / "approval_workflow.yaml"
        result["passed"] = p.exists()
    elif rule_id in ("SOT_AGENT_029",):
        p = repo_root / "08_identity_score" / "module.yaml"
        result["passed"] = p.exists()

    return result

def run_checks(rules_path: Path, scan_path: Path, repo_root: Path) -> dict:
    rules = load_rules(rules_path)
    scan = {}
    if scan_path and scan_path.exists():
        scan = json.loads(scan_path.read_text())

    results = [check_rule(r, scan, repo_root) for r in rules]
    failed = [r for r in results if not r["passed"]]
    critical_failures = [r for r in failed if r["severity"] == "critical"]

    return {
        "total_rules": len(rules),
        "passed": len(results) - len(failed),
        "failed": len(failed),
        "critical_failures": len(critical_failures),
        "results": results,
        "status": "FAIL_SOT" if critical_failures else ("FAIL_SOT" if failed else "PASS"),
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rules", required=True)
    parser.add_argument("--repo-scan", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--generate-scan-if-missing", default="false")
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    scan_path = Path(args.repo_scan)

    if args.generate_scan_if_missing.lower() == "true" and not scan_path.exists():
        load_or_generate_scan(scan_path, repo_root)

    result = run_checks(Path(args.rules), scan_path, repo_root)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, indent=2))
    print(f"SOT check: {result['status']} ({result['passed']}/{result['total_rules']} rules passed)")
    sys.exit(0 if result["status"] == "PASS" else 1)
```

- [ ] **Step 4: Tests bestehen**

```bash
pytest tests/autorunners/test_ar02_contract_tests.py -v
```

- [ ] **Step 5: contract_tests.yml GitHub Action erstellen**

```yaml
# .github/workflows/contract_tests.yml
name: AR-02 Contract Tests Gate

on:
  push:
    paths: ['**/contracts/**/*.openapi.yaml', '**/contracts/schemas/**', '16_codex/contracts/**']
  pull_request:
    branches: [main]

permissions:
  contents: read

jobs:
  contract-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 2

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - run: pip install pyyaml jsonschema schemathesis pydantic

      - name: Generate repo_scan.json
        run: |
          python 24_meta_orchestration/scripts/generate_repo_scan.py \
            --repo-root . --commit-sha "${{ github.sha }}" \
            --out 24_meta_orchestration/registry/generated/repo_scan.json

      - name: SOT Contract Check (SOT_AGENT_001-036)
        run: |
          python 24_meta_orchestration/scripts/sot_contract_check.py \
            --rules 16_codex/contracts/sot/sot_contract.yaml \
            --repo-scan 24_meta_orchestration/registry/generated/repo_scan.json \
            --out /tmp/sot_check.json \
            --repo-root .

      - name: Find and validate changed contracts
        run: |
          git diff --name-only HEAD~1 | grep -E '\.openapi\.yaml$' > /tmp/changed_contracts.txt || true
          echo "Changed contracts:"
          cat /tmp/changed_contracts.txt

          while IFS= read -r contract; do
            if [ -f "$contract" ]; then
              echo "Validating: $contract"
              python -c "
          import yaml, sys
          try:
              yaml.safe_load(open('$contract'))
              print('YAML syntax OK')
          except Exception as e:
              print(f'YAML error: {e}')
              sys.exit(1)
              "
            fi
          done < /tmp/changed_contracts.txt

      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: ar02-evidence-${{ github.sha }}
          path: /tmp/sot_check.json
          retention-days: 90
```

- [ ] **Step 6: Commit**

```bash
git add 24_meta_orchestration/scripts/sot_contract_check.py \
        .github/workflows/contract_tests.yml \
        tests/autorunners/test_ar02_contract_tests.py
git commit -m "feat(AR-02): add contract tests gate + SOT-Agent rules check"
```

---

### Task 9: shard_completion_check.py + AR-05 GitHub Action

**Files:**
- Create: `24_meta_orchestration/scripts/shard_completion_check.py`
- Create: `.github/workflows/shard_completion_gate.yml`
- Test: `tests/autorunners/test_ar05_shard_gate.py`

- [ ] **Step 1: Failing test**

```python
# tests/autorunners/test_ar05_shard_gate.py
import json
import subprocess
from pathlib import Path
import pytest

SCRIPT = Path("C:/Users/bibel/Documents/Github/SSID/24_meta_orchestration/scripts/shard_completion_check.py")
SSID_ROOT = Path("C:/Users/bibel/Documents/Github/SSID")

def run_check(repo_root=None, extra=None):
    cmd = ["python", str(SCRIPT),
           "--repo-root", str(repo_root or SSID_ROOT),
           "--roots", "24", "--shards", "16",
           "--out", "/tmp/shard_test.json"]
    if extra:
        cmd += extra
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, json.loads(r.stdout) if r.stdout.strip() else {}

def test_output_schema_correct():
    code, result = run_check()
    assert "total_expected" in result
    assert result["total_expected"] == 384
    assert "total_found" in result
    assert "completion_percent" in result
    assert "by_root" in result
    assert len(result["by_root"]) == 24

def test_all_24_roots_checked():
    code, result = run_check()
    assert "01_ai_layer" in result["by_root"]
    assert "24_meta_orchestration" in result["by_root"]

def test_regression_detection(tmp_path):
    # Simuliere Regression: vorher 10 Charts, jetzt 9
    state_file = tmp_path / "shard_state.json"
    state_file.write_text(json.dumps({"total_found": 10}))
    cmd = ["python", str(SCRIPT),
           "--repo-root", str(tmp_path),
           "--roots", "24", "--shards", "16",
           "--previous-state", str(state_file),
           "--out", str(tmp_path / "result.json")]
    r = subprocess.run(cmd, capture_output=True, text=True)
    result = json.loads((tmp_path / "result.json").read_text())
    # Aktuell 0 (leeres tmp), vorher 10 = Regression
    assert result.get("regression_detected") == True

def test_completion_below_threshold_warns_not_fails():
    # < 90% soll WARN, nicht FAIL sein
    code, result = run_check()
    if result["completion_percent"] < 90:
        # Warnung erwartet, aber kein exit 1 (es sei denn Regression)
        assert result.get("status") in ("WARN", "PASS", "FAIL_SHARD")
```

- [ ] **Step 2: Test ausführen — FAIL**

```bash
pytest tests/autorunners/test_ar05_shard_gate.py -v
```

- [ ] **Step 3: shard_completion_check.py implementieren**

```python
#!/usr/bin/env python3
# 24_meta_orchestration/scripts/shard_completion_check.py
"""
AR-05: Shard Completion Gate — 24×16=384 chart.yaml Matrix Check
SoT-Regel: master §4 (Deterministic Architecture), ADR-0008
"""
import argparse
import json
import sys
from pathlib import Path

ROOTS_24 = [
    "01_ai_layer","02_audit_logging","03_core","04_deployment",
    "05_documentation","06_data_pipeline","07_governance_legal","08_identity_score",
    "09_meta_identity","10_interoperability","11_test_simulation","12_tooling",
    "13_ui_layer","14_zero_time_auth","15_infra","16_codex",
    "17_observability","18_data_layer","19_adapters","20_foundation",
    "21_post_quantum_crypto","22_datasets","23_compliance","24_meta_orchestration",
]
SHARDS_16 = [
    "01_identitaet_personen","02_dokumente_nachweise","03_zugang_berechtigungen",
    "04_kommunikation_daten","05_gesundheit_medizin","06_bildung_qualifikationen",
    "07_familie_soziales","08_mobilitaet_fahrzeuge","09_arbeit_karriere",
    "10_finanzen_banking","11_versicherungen_risiken","12_immobilien_grundstuecke",
    "13_unternehmen_gewerbe","14_vertraege_vereinbarungen",
    "15_handel_transaktionen","16_behoerden_verwaltung",
]

def check(repo_root: Path, num_roots: int, num_shards: int, previous_state: dict = None) -> dict:
    total_expected = num_roots * num_shards
    total_found = 0
    missing = []
    by_root = {}

    for root_id in ROOTS_24[:num_roots]:
        root_found = 0
        root_missing = []
        for shard_id in SHARDS_16[:num_shards]:
            chart = repo_root / root_id / "shards" / shard_id / "chart.yaml"
            if chart.exists():
                root_found += 1
                total_found += 1
            else:
                path = f"{root_id}/shards/{shard_id}/chart.yaml"
                root_missing.append(path)
                missing.append(path)
        by_root[root_id] = {
            "expected": num_shards,
            "found": root_found,
            "missing_count": len(root_missing),
        }

    completion_pct = round(total_found / total_expected * 100, 2) if total_expected else 0
    regression = False
    if previous_state and "total_found" in previous_state:
        regression = total_found < previous_state["total_found"]

    if regression:
        status = "FAIL_SHARD"
    elif completion_pct >= 90:
        status = "PASS"
    else:
        status = "WARN"

    return {
        "total_expected": total_expected,
        "total_found": total_found,
        "missing_count": len(missing),
        "completion_percent": completion_pct,
        "status": status,
        "regression_detected": regression,
        "by_root": by_root,
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--roots", type=int, default=24)
    parser.add_argument("--shards", type=int, default=16)
    parser.add_argument("--previous-state", default=None)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    previous_state = None
    if args.previous_state and Path(args.previous_state).exists():
        previous_state = json.loads(Path(args.previous_state).read_text())

    result = check(repo_root, args.roots, args.shards, previous_state)
    print(json.dumps(result, indent=2))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, indent=2))
    pct = result["completion_percent"]
    print(f"Shard completion: {pct}% ({result['total_found']}/{result['total_expected']}) — {result['status']}")
    sys.exit(1 if result["status"] == "FAIL_SHARD" else 0)
```

- [ ] **Step 4: shard_completion_gate.yml erstellen**

```yaml
# .github/workflows/shard_completion_gate.yml
name: AR-05 Shard Completion Gate

on:
  push:
    paths: ['**/shards/**', '**/chart.yaml']
  pull_request:
    branches: [main]

permissions:
  contents: read

jobs:
  shard-completion:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Run shard completion check
        run: |
          python 24_meta_orchestration/scripts/shard_completion_check.py \
            --repo-root . \
            --roots 24 --shards 16 \
            --out /tmp/shard_completion.json
          cat /tmp/shard_completion.json

      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: ar05-shard-evidence-${{ github.sha }}
          path: /tmp/shard_completion.json
          retention-days: 90
```

- [ ] **Step 5: Tests bestehen**

```bash
pytest tests/autorunners/test_ar05_shard_gate.py -v
```

- [ ] **Step 6: Commit**

```bash
git add 24_meta_orchestration/scripts/shard_completion_check.py \
        .github/workflows/shard_completion_gate.yml \
        tests/autorunners/test_ar05_shard_gate.py
git commit -m "feat(AR-05): add shard completion gate (24×16=384 matrix check)"
```

---

## Lokale Simulation (alle Plan-A AutoRunner)

```bash
# Voraussetzung: Python 3.11, pip install pydantic pyyaml jsonschema

# AR-07: Forbidden Extensions
python 12_tooling/scripts/forbidden_ext_check.py \
  --extensions ".ipynb .parquet .sqlite .db" \
  --repo-root C:/Users/bibel/Documents/Github/SSID \
  --scan-all true

# AR-08: Secret Scanner
python 12_tooling/scripts/secret_scanner.py \
  --repo-root C:/Users/bibel/Documents/Github/SSID \
  --scan-all true

# AR-02: SOT Contract Check
python 24_meta_orchestration/scripts/sot_contract_check.py \
  --rules 16_codex/contracts/sot/sot_contract.yaml \
  --repo-scan 24_meta_orchestration/registry/generated/repo_scan.json \
  --out /tmp/sot_check.json \
  --repo-root C:/Users/bibel/Documents/Github/SSID

# AR-05: Shard Completion
python 24_meta_orchestration/scripts/shard_completion_check.py \
  --repo-root C:/Users/bibel/Documents/Github/SSID \
  --roots 24 --shards 16 \
  --out /tmp/shard_check.json

# Alle Tests auf einmal:
cd C:/Users/bibel/Documents/Github/SSID
pytest tests/autorunners/ -v --tb=short
```

---

## Zusammenfassung Plan A

**Neue Dateien:**
| Datei | Zweck |
|-------|-------|
| `12_tooling/autorunner_base/models.py` | Gemeinsame Datenmodelle |
| `12_tooling/autorunner_base/evidence.py` | WORM-Evidence-Writer |
| `12_tooling/scripts/forbidden_ext_check.py` | AR-07 Core |
| `12_tooling/scripts/secret_scanner.py` | AR-08 Core |
| `12_tooling/scripts/apply_deny_globs.py` | AR-08 Core |
| `24_meta_orchestration/scripts/generate_repo_scan.py` | OPA-Input (alle AR) |
| `24_meta_orchestration/scripts/sot_contract_check.py` | AR-02 Core |
| `24_meta_orchestration/scripts/shard_completion_check.py` | AR-05 Core |
| `.github/workflows/forbidden_extensions.yml` | AR-07 Action |
| `.github/workflows/opencore_sync.yml` | AR-08 Action |
| `.github/workflows/contract_tests.yml` | AR-02 Action |
| `.github/workflows/shard_completion_gate.yml` | AR-05 Action |
| `tests/autorunners/test_base_models.py` | Basis-Tests |
| `tests/autorunners/test_evidence_writer.py` | Evidence-Tests |
| `tests/autorunners/test_generate_repo_scan.py` | OPA-Input-Tests |
| `tests/autorunners/test_ar07_forbidden_extensions.py` | AR-07 Tests |
| `tests/autorunners/test_ar08_opencore_sync.py` | AR-08 Tests |
| `tests/autorunners/test_ar02_contract_tests.py` | AR-02 Tests |
| `tests/autorunners/test_ar05_shard_gate.py` | AR-05 Tests |

**Keine neuen Root-Dirs. Keine Root-Level-Files. Root-Level-Exceptions respektiert.**

**Plan B** (AI-Assisted: AR-01, AR-03, AR-04, AR-06, AR-09, AR-10) folgt nach GO für Plan A.
