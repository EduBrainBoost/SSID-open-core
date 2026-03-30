# TS013 + TS014 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor shard manifest builder to be parametric (all 24 roots), add shared lib, create full conformance gate CLI for pilot shards, with fixture-based testing and CI integration.

**Architecture:** Shared lib `_lib/shards.py` provides deterministic scan/parse/validate primitives. Three separate CLIs (`shard_manifest_build.py`, `shard_gate_chart_manifest.py`, `shard_conformance_gate.py`) consume it. Gate chain in `run_all_gates.py` extended with conformance gate.

**Tech Stack:** Python 3, PyYAML, jsonschema (Draft 2020-12), pytest, unittest

**Base branch:** Merge `feat/l1-hybridc-pilot` into working branch first (contains existing manifest builder, gate, contracts, and conformance tests that will be refactored).

---

### Task 0: Merge existing hybridc branch

**Why:** `feat/l1-hybridc-pilot` contains `shard_manifest_build.py`, `shard_gate_chart_manifest.py`, contract schemas, and conformance tests. We build on this.

**Step 1: Merge**

```bash
cd "C:\Users\bibel\Documents\Github\SSID"
git merge feat/l1-hybridc-pilot --no-edit
```

**Step 2: Verify merge succeeded**

```bash
git log --oneline -5
git ls-files "12_tooling/cli/shard_manifest_build.py"
```

Expected: file exists in index

**Step 3: Commit** (if merge commit needed — merge should auto-commit)

---

### Task 1: Create `_lib/shards.py` shared primitives

**Files:**
- Create: `12_tooling/cli/_lib/__init__.py`
- Create: `12_tooling/cli/_lib/shards.py`
- Test: `11_test_simulation/tests_compliance/test_lib_shards.py`

**Step 1: Restore shard directories needed for testing**

```bash
cd "C:\Users\bibel\Documents\Github\SSID"
git checkout HEAD -- 03_core/shards/01_identitaet_personen/
git checkout HEAD -- 03_core/shards/02_dokumente_nachweise/
git checkout HEAD -- 12_tooling/cli/
```

**Step 2: Write the failing test**

```python
#!/usr/bin/env python3
"""Unit tests for _lib/shards.py shared primitives."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import yaml

# Ensure cli/ is importable
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "12_tooling" / "cli"))

from _lib.shards import (
    ROOTS_24,
    find_roots,
    find_shards,
    parse_yaml,
    parse_json_schema,
    validate_manifest_fields,
    check_pii_keys,
    write_yaml,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestRoots24(unittest.TestCase):
    def test_count(self):
        self.assertEqual(len(ROOTS_24), 24)

    def test_sorted(self):
        self.assertEqual(ROOTS_24, sorted(ROOTS_24))

    def test_known_roots(self):
        self.assertIn("03_core", ROOTS_24)
        self.assertIn("12_tooling", ROOTS_24)
        self.assertIn("24_meta_orchestration", ROOTS_24)


class TestFindRoots(unittest.TestCase):
    def test_finds_roots(self):
        roots = find_roots(REPO_ROOT)
        root_names = [r.name for r in roots]
        self.assertIn("03_core", root_names)
        self.assertEqual(root_names, sorted(root_names))


class TestFindShards(unittest.TestCase):
    def test_finds_shards_in_core(self):
        core = REPO_ROOT / "03_core"
        shards = find_shards(core)
        shard_names = [s.name for s in shards]
        self.assertIn("01_identitaet_personen", shard_names)
        self.assertEqual(shard_names, sorted(shard_names))

    def test_empty_for_missing_root(self):
        shards = find_shards(REPO_ROOT / "nonexistent_root")
        self.assertEqual(shards, [])


class TestParseYaml(unittest.TestCase):
    def test_valid_yaml(self):
        chart = REPO_ROOT / "03_core" / "shards" / "01_identitaet_personen" / "chart.yaml"
        data = parse_yaml(chart)
        self.assertIsNotNone(data)
        self.assertIn("version", data)

    def test_missing_file(self):
        self.assertIsNone(parse_yaml(Path("/nonexistent.yaml")))


class TestParseJsonSchema(unittest.TestCase):
    def test_valid_schema(self):
        schema_path = (
            REPO_ROOT / "03_core" / "shards" / "01_identitaet_personen"
            / "contracts" / "identity_proof.schema.json"
        )
        schema = parse_json_schema(schema_path)
        self.assertIsNotNone(schema)
        self.assertIn("$schema", schema)

    def test_missing_file(self):
        self.assertIsNone(parse_json_schema(Path("/nonexistent.json")))


class TestValidateManifestFields(unittest.TestCase):
    def test_valid_manifest(self):
        data = {
            "shard_id": "01_identitaet_personen",
            "root_id": "03_core",
            "version": "1.0.0",
            "implementation_stack": "generated",
            "contracts": [],
            "conformance": [],
            "policies": [],
        }
        errors = validate_manifest_fields(data)
        self.assertEqual(errors, [])

    def test_missing_fields(self):
        errors = validate_manifest_fields({})
        self.assertEqual(len(errors), 7)


class TestCheckPiiKeys(unittest.TestCase):
    def test_clean_schema(self):
        schema = {"properties": {"proof_hash": {}, "hash_alg": {}}}
        self.assertEqual(check_pii_keys(schema), [])

    def test_pii_detected(self):
        schema = {"properties": {"name": {}, "email": {}, "proof_hash": {}}}
        violations = check_pii_keys(schema)
        self.assertIn("name", violations)
        self.assertIn("email", violations)
        self.assertNotIn("proof_hash", violations)


class TestWriteYaml(unittest.TestCase):
    def test_writes_new_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.yaml"
            result = write_yaml(path, {"key": "value"})
            self.assertTrue(result)
            self.assertTrue(path.exists())
            content = path.read_text(encoding="utf-8")
            self.assertIn("key: value", content)
            self.assertNotIn("\r\n", content)  # LF only

    def test_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.yaml"
            path.write_text("existing", encoding="utf-8")
            result = write_yaml(path, {"key": "new"})
            self.assertFalse(result)
            self.assertEqual(path.read_text(encoding="utf-8"), "existing")


if __name__ == "__main__":
    unittest.main()
```

**Step 3: Run test to verify it fails**

Run: `cd "C:\Users\bibel\Documents\Github\SSID" && python -m pytest 11_test_simulation/tests_compliance/test_lib_shards.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named '_lib'`

**Step 4: Implement `_lib/__init__.py`**

```python
# 12_tooling/cli/_lib/__init__.py
```

(empty file)

**Step 5: Implement `_lib/shards.py`**

```python
#!/usr/bin/env python3
"""Shared shard scanning, parsing, and validation primitives."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

ROOTS_24: list[str] = [
    "01_ai_layer",
    "02_audit_logging",
    "03_core",
    "04_deployment",
    "05_documentation",
    "06_data_pipeline",
    "07_governance_legal",
    "08_identity_score",
    "09_meta_identity",
    "10_interoperability",
    "11_test_simulation",
    "12_tooling",
    "13_ui_layer",
    "14_zero_time_auth",
    "15_infra",
    "16_codex",
    "17_observability",
    "18_data_layer",
    "19_adapters",
    "20_foundation",
    "21_post_quantum_crypto",
    "22_datasets",
    "23_compliance",
    "24_meta_orchestration",
]

MANIFEST_REQUIRED_FIELDS: list[str] = [
    "shard_id",
    "root_id",
    "version",
    "implementation_stack",
    "contracts",
    "conformance",
    "policies",
]

PII_DENY_KEYS: list[str] = [
    "name",
    "birth",
    "address",
    "doc_number",
    "email",
    "url",
]


def find_roots(repo_root: Path) -> list[Path]:
    """Return all 24 canonical root directories (sorted)."""
    return sorted(
        repo_root / name
        for name in ROOTS_24
        if (repo_root / name).is_dir()
    )


def find_shards(root_path: Path) -> list[Path]:
    """Return shard directories under <root>/shards/ (sorted)."""
    shards_dir = root_path / "shards"
    if not shards_dir.is_dir():
        return []
    return sorted(d for d in shards_dir.iterdir() if d.is_dir())


def parse_yaml(path: Path) -> dict[str, Any] | None:
    """Safe YAML parse. Returns None on any error."""
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def parse_json_schema(path: Path) -> dict[str, Any] | None:
    """Safe JSON parse with basic Draft-2020-12 structure check."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        return data
    except Exception:
        return None


def validate_manifest_fields(data: dict[str, Any]) -> list[str]:
    """Check that all required manifest fields are present. Returns list of missing field names."""
    return [f for f in MANIFEST_REQUIRED_FIELDS if f not in data]


def check_pii_keys(schema: dict[str, Any]) -> list[str]:
    """Check schema property keys against PII deny list. Returns violating key names."""
    props = schema.get("properties", {})
    return [k for k in props if k.lower() in PII_DENY_KEYS]


def write_yaml(path: Path, data: dict[str, Any]) -> bool:
    """Write YAML file (UTF-8, LF). Returns False if file exists (no-overwrite)."""
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    content = yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)
    # Ensure LF line endings
    content = content.replace("\r\n", "\n")
    path.write_bytes(content.encode("utf-8"))
    return True
```

**Step 6: Run tests and verify PASS**

Run: `cd "C:\Users\bibel\Documents\Github\SSID" && python -m pytest 11_test_simulation/tests_compliance/test_lib_shards.py -v`
Expected: All PASS

**Step 7: Commit**

```bash
git add 12_tooling/cli/_lib/__init__.py 12_tooling/cli/_lib/shards.py 11_test_simulation/tests_compliance/test_lib_shards.py
git commit -m "feat(ts013): add _lib/shards.py shared primitives with tests"
```

---

### Task 2: Rewrite `shard_manifest_build.py` (parametric, shard-level output)

**Files:**
- Modify: `12_tooling/cli/shard_manifest_build.py` (full rewrite)
- Test: `11_test_simulation/tests_compliance/test_shard_manifest_build.py`

**Step 1: Write the failing test**

```python
#!/usr/bin/env python3
"""Tests for shard_manifest_build.py (parametric, shard-level output)."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "12_tooling" / "cli" / "shard_manifest_build.py"


class TestManifestBuildCLI(unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    def test_no_args_shows_help_or_dryrun(self):
        """Without --root or --all, should show help or dry-run info."""
        proc = self._run()
        self.assertEqual(proc.returncode, 0)
        self.assertIn("INFO", proc.stdout)

    def test_root_dryrun(self):
        """--root 03_core without --apply = dry-run only."""
        proc = self._run("--root", "03_core")
        self.assertEqual(proc.returncode, 0)
        # Should not create files (dry-run)
        self.assertNotIn("CREATED:", proc.stdout)

    def test_root_flag_validates_name(self):
        """--root with invalid name = error."""
        proc = self._run("--root", "99_nonexistent")
        self.assertNotEqual(proc.returncode, 0)

    def test_apply_requires_root_or_all(self):
        """--apply without --root or --all = error."""
        proc = self._run("--apply")
        self.assertNotEqual(proc.returncode, 0)


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `cd "C:\Users\bibel\Documents\Github\SSID" && python -m pytest 11_test_simulation/tests_compliance/test_shard_manifest_build.py -v`
Expected: FAIL (old CLI has --write not --root/--apply)

**Step 3: Rewrite `shard_manifest_build.py`**

```python
#!/usr/bin/env python3
"""
Shard Manifest Builder — scans chart.yaml files, generates missing shard-level manifest.yaml.
Additiv-only: never overwrites existing manifests. Duplicate guard.
Default: dry-run (no --apply = read-only). Use --apply to persist.

Output: <root>/shards/<shard>/manifest.yaml (next to chart.yaml)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib.shards import (
    ROOTS_24,
    find_roots,
    find_shards,
    parse_yaml,
    write_yaml,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def discover_contracts(shard_dir: Path) -> list[str]:
    """Find contract schema paths relative to shard dir."""
    contracts_dir = shard_dir / "contracts"
    if not contracts_dir.is_dir():
        return []
    return sorted(
        str(p.relative_to(shard_dir))
        for p in contracts_dir.glob("*.schema.json")
    )


def discover_conformance(shard_dir: Path) -> list[str]:
    """Find conformance test paths relative to shard dir."""
    conf_dir = shard_dir / "conformance"
    if not conf_dir.is_dir():
        return []
    return sorted(
        str(p.relative_to(shard_dir))
        for p in conf_dir.glob("test_*.py")
    )


def derive_policies(chart: dict) -> list[dict]:
    """Extract policy refs from chart.yaml policies list."""
    policies = chart.get("policies", [])
    return [{"ref": p["id"]} for p in policies if isinstance(p, dict) and "id" in p]


def generate_manifest(shard_dir: Path, root_name: str, chart: dict) -> dict:
    """Generate manifest.yaml content from chart.yaml + filesystem."""
    return {
        "shard_id": shard_dir.name,
        "root_id": root_name,
        "version": chart.get("version", "0.1.0"),
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "implementation_stack": "generated",
        "contracts": discover_contracts(shard_dir),
        "conformance": discover_conformance(shard_dir),
        "policies": derive_policies(chart),
    }


def process_root(root_path: Path, apply: bool) -> dict:
    """Process all shards in a root. Returns {created: [], skipped: [], errors: []}."""
    result = {"created": [], "skipped": [], "errors": []}
    root_name = root_path.name
    shards = find_shards(root_path)

    for shard_dir in shards:
        chart_path = shard_dir / "chart.yaml"
        manifest_path = shard_dir / "manifest.yaml"

        if not chart_path.exists():
            result["errors"].append(f"{shard_dir.name}: missing chart.yaml")
            continue

        if manifest_path.exists():
            result["skipped"].append(shard_dir.name)
            print(f"SKIP (exists): {root_name}/shards/{shard_dir.name}/manifest.yaml")
            continue

        chart = parse_yaml(chart_path)
        if chart is None:
            result["errors"].append(f"{shard_dir.name}: chart.yaml not parseable")
            continue

        manifest = generate_manifest(shard_dir, root_name, chart)

        if apply:
            if write_yaml(manifest_path, manifest):
                result["created"].append(shard_dir.name)
                print(f"CREATED: {root_name}/shards/{shard_dir.name}/manifest.yaml")
            else:
                result["skipped"].append(shard_dir.name)
                print(f"SKIP (duplicate guard): {root_name}/shards/{shard_dir.name}/manifest.yaml")
        else:
            result["created"].append(shard_dir.name)
            print(f"WOULD CREATE: {root_name}/shards/{shard_dir.name}/manifest.yaml")

    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Shard Manifest Builder (parametric, additiv-only, no-overwrite)"
    )
    parser.add_argument("--root", type=str, help="Process single root (e.g. 03_core)")
    parser.add_argument("--all", action="store_true", dest="all_roots", help="Process all 24 roots")
    parser.add_argument("--apply", action="store_true", help="Write manifests (default: dry-run)")
    parser.add_argument("--report", type=str, help="Write JSON report to path")
    args = parser.parse_args()

    # Validation
    if args.apply and not args.root and not args.all_roots:
        print("ERROR: --apply requires --root <name> or --all")
        return 2

    if args.root and args.root not in ROOTS_24:
        print(f"ERROR: Unknown root '{args.root}'. Valid: {', '.join(ROOTS_24)}")
        return 2

    if not args.root and not args.all_roots:
        print("INFO: No --root or --all specified. Use --root <name> or --all to scan.")
        print(f"INFO: Available roots ({len(ROOTS_24)}): {', '.join(ROOTS_24)}")
        return 0

    # Determine roots to process
    if args.all_roots:
        roots = find_roots(REPO_ROOT)
    else:
        root_path = REPO_ROOT / args.root
        if not root_path.is_dir():
            print(f"ERROR: Root directory not found: {root_path}")
            return 2
        roots = [root_path]

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"INFO: Mode={mode}, Roots={len(roots)}")

    all_results = {}
    for root_path in roots:
        result = process_root(root_path, args.apply)
        all_results[root_path.name] = result

    # Summary
    total_created = sum(len(r["created"]) for r in all_results.values())
    total_skipped = sum(len(r["skipped"]) for r in all_results.values())
    total_errors = sum(len(r["errors"]) for r in all_results.values())
    print(f"\nSummary: {total_created} created, {total_skipped} skipped, {total_errors} errors")

    # Report
    if args.report:
        Path(args.report).write_text(
            json.dumps(all_results, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"Report written to: {args.report}")

    return 1 if total_errors > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

**Step 4: Run tests and verify PASS**

Run: `cd "C:\Users\bibel\Documents\Github\SSID" && python -m pytest 11_test_simulation/tests_compliance/test_shard_manifest_build.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add 12_tooling/cli/shard_manifest_build.py 11_test_simulation/tests_compliance/test_shard_manifest_build.py
git commit -m "feat(ts013): rewrite shard_manifest_build.py (parametric, shard-level output)"
```

---

### Task 3: Update `shard_gate_chart_manifest.py` (shard-level manifest recognition)

**Files:**
- Modify: `12_tooling/cli/shard_gate_chart_manifest.py`

**Step 1: Modify `check_shard()` to recognize shard-level manifest**

Replace the `has_manifest` check:

```python
# OLD:
has_manifest = any(
    m for m in shard_dir.glob("implementations/*/manifest.yaml")
)

# NEW: Check shard-level first, then fallback to implementations/
has_manifest = (shard_dir / "manifest.yaml").exists() or any(
    m for m in shard_dir.glob("implementations/*/manifest.yaml")
)
```

Also add `sys.path` and import from `_lib.shards`:

```python
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib.shards import ROOTS_24, find_shards, parse_yaml
```

And make SHARDS_ROOT parametric (accept --root flag, default to 03_core for backward compat).

**Step 2: Run existing test (should still pass)**

Run: `cd "C:\Users\bibel\Documents\Github\SSID" && python 12_tooling/cli/shard_gate_chart_manifest.py`
Expected: PASS (existing behavior preserved)

**Step 3: Commit**

```bash
git add 12_tooling/cli/shard_gate_chart_manifest.py
git commit -m "feat(ts013): update shard gate to recognize shard-level manifest.yaml"
```

---

### Task 4: Create conformance fixtures (pilot shards)

**Files:**
- Create: `03_core/shards/01_identitaet_personen/conformance/fixtures/valid.json`
- Create: `03_core/shards/01_identitaet_personen/conformance/fixtures/invalid_pii.json`
- Create: `03_core/shards/01_identitaet_personen/conformance/fixtures/invalid_format.json`
- Create: `03_core/shards/02_dokumente_nachweise/conformance/fixtures/valid.json`
- Create: `03_core/shards/02_dokumente_nachweise/conformance/fixtures/invalid_pii.json`
- Create: `03_core/shards/02_dokumente_nachweise/conformance/fixtures/invalid_format.json`

**Step 1: Create Shard 01 fixtures**

`valid.json`:
```json
{
  "schema_version": "1.0.0",
  "proof_hash": "0x0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "hash_alg": "sha256",
  "identity_type": "person",
  "issuer_id": "did:example:issuer123",
  "issued_at_utc": "2026-03-02T12:00:00Z"
}
```

`invalid_pii.json`:
```json
{
  "schema_version": "1.0.0",
  "proof_hash": "0x0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "hash_alg": "sha256",
  "identity_type": "person",
  "issued_at_utc": "2026-03-02T12:00:00Z",
  "name": "John Doe",
  "email": "john@example.com"
}
```

`invalid_format.json`:
```json
{
  "schema_version": "1.0.0",
  "proof_hash": "0123456789abcdef",
  "hash_alg": "md5",
  "identity_type": "robot",
  "issued_at_utc": "2026-03-02 12:00:00"
}
```

**Step 2: Create Shard 02 fixtures**

`valid.json`:
```json
{
  "schema_version": "1.0.0",
  "doc_hash": "0xabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcd",
  "hash_alg": "keccak256",
  "doc_type": "credential",
  "issued_at_utc": "2026-03-02T12:00:00Z"
}
```

`invalid_pii.json`:
```json
{
  "schema_version": "1.0.0",
  "doc_hash": "0xabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcd",
  "hash_alg": "keccak256",
  "doc_type": "credential",
  "issued_at_utc": "2026-03-02T12:00:00Z",
  "address": "123 Main St",
  "doc_number": "AB12345"
}
```

`invalid_format.json`:
```json
{
  "schema_version": "1.0.0",
  "doc_hash": "abcdef",
  "hash_alg": "md5",
  "doc_type": "passport",
  "issued_at_utc": "March 2, 2026"
}
```

**Step 3: Commit**

```bash
git add 03_core/shards/01_identitaet_personen/conformance/ 03_core/shards/02_dokumente_nachweise/conformance/
git commit -m "test(ts014): add conformance fixtures for pilot shards (valid + invalid_pii + invalid_format)"
```

---

### Task 5: Create `shard_conformance_gate.py`

**Files:**
- Create: `12_tooling/cli/shard_conformance_gate.py`
- Test: `11_test_simulation/tests_compliance/test_shard_conformance_gate.py`

**Step 1: Write the failing test**

```python
#!/usr/bin/env python3
"""Tests for shard_conformance_gate.py (full conformance gate CLI)."""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "12_tooling" / "cli" / "shard_conformance_gate.py"


class TestConformanceGateCLI(unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    def test_pilot_shard_01_passes(self):
        proc = self._run("--root", "03_core", "--shard", "01_identitaet_personen")
        self.assertEqual(proc.returncode, 0, f"STDOUT: {proc.stdout}\nSTDERR: {proc.stderr}")

    def test_pilot_shard_02_passes(self):
        proc = self._run("--root", "03_core", "--shard", "02_dokumente_nachweise")
        self.assertEqual(proc.returncode, 0, f"STDOUT: {proc.stdout}\nSTDERR: {proc.stderr}")

    def test_report_json_valid(self):
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            report_path = f.name
        proc = self._run("--root", "03_core", "--shard", "01_identitaet_personen", "--report", report_path)
        self.assertEqual(proc.returncode, 0)
        report = json.loads(Path(report_path).read_text(encoding="utf-8"))
        self.assertEqual(report["verdict"], "PASS")
        self.assertIn("checks", report)
        self.assertNotIn("score", json.dumps(report))

    def test_invalid_shard_name(self):
        proc = self._run("--root", "03_core", "--shard", "99_nonexistent")
        self.assertEqual(proc.returncode, 2)

    def test_no_scores_in_output(self):
        """Report must contain PASS/FAIL and lists/counts only, no scores."""
        proc = self._run("--root", "03_core", "--shard", "01_identitaet_personen")
        self.assertNotIn("score", proc.stdout.lower())
        self.assertNotIn("percent", proc.stdout.lower())


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `cd "C:\Users\bibel\Documents\Github\SSID" && python -m pytest 11_test_simulation/tests_compliance/test_shard_conformance_gate.py -v`
Expected: FAIL (script does not exist)

**Step 3: Implement `shard_conformance_gate.py`**

```python
#!/usr/bin/env python3
"""
Shard Conformance Gate — structure + schema + fixture validation.
Exit 0 = PASS, Exit 1 = FAIL, Exit 2 = ERROR.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import jsonschema
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib.shards import (
    ROOTS_24,
    find_shards,
    parse_yaml,
    parse_json_schema,
    validate_manifest_fields,
    check_pii_keys,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def check_structure(shard_dir: Path) -> dict:
    """A) Structure conformance: chart, manifest, contracts."""
    verdict = "PASS"
    checked = []
    violations = []

    # chart.yaml
    chart_path = shard_dir / "chart.yaml"
    checked.append("chart.yaml")
    if not chart_path.exists():
        violations.append("chart.yaml missing")
        verdict = "FAIL"
    elif parse_yaml(chart_path) is None:
        violations.append("chart.yaml not YAML-parseable")
        verdict = "FAIL"

    # manifest.yaml
    manifest_path = shard_dir / "manifest.yaml"
    checked.append("manifest.yaml")
    if not manifest_path.exists():
        violations.append("manifest.yaml missing")
        verdict = "FAIL"
    else:
        data = parse_yaml(manifest_path)
        if data is None:
            violations.append("manifest.yaml not YAML-parseable")
            verdict = "FAIL"
        else:
            missing = validate_manifest_fields(data)
            if missing:
                violations.append(f"manifest.yaml missing fields: {', '.join(missing)}")
                verdict = "FAIL"

    # contracts/*.schema.json
    contracts_dir = shard_dir / "contracts"
    if contracts_dir.is_dir():
        for schema_path in sorted(contracts_dir.glob("*.schema.json")):
            rel = str(schema_path.relative_to(shard_dir))
            checked.append(rel)
            schema = parse_json_schema(schema_path)
            if schema is None:
                violations.append(f"{rel}: not JSON-parseable")
                verdict = "FAIL"
                continue
            # Draft check
            if "$schema" not in schema:
                violations.append(f"{rel}: missing $schema field")
                verdict = "FAIL"
            # PII check
            pii = check_pii_keys(schema)
            if pii:
                violations.append(f"{rel}: PII keys found: {', '.join(pii)}")
                verdict = "FAIL"

    return {"verdict": verdict, "checked_files": checked, "violations": violations}


def check_schema_validation(shard_dir: Path) -> dict:
    """B-partial) Validate that contract schemas are structurally valid JSON Schema."""
    verdict = "PASS"
    checked = []
    violations = []

    contracts_dir = shard_dir / "contracts"
    if not contracts_dir.is_dir():
        return {"verdict": "FAIL", "checked_files": [], "violations": ["no contracts/ directory"]}

    for schema_path in sorted(contracts_dir.glob("*.schema.json")):
        rel = str(schema_path.relative_to(shard_dir))
        checked.append(rel)
        schema = parse_json_schema(schema_path)
        if schema is None:
            violations.append(f"{rel}: not parseable")
            verdict = "FAIL"
            continue
        # Try to compile the schema
        try:
            jsonschema.Draft202012Validator.check_schema(schema)
        except jsonschema.SchemaError as e:
            violations.append(f"{rel}: invalid schema: {e.message}")
            verdict = "FAIL"

    return {"verdict": verdict, "checked_files": checked, "violations": violations}


def check_fixtures(shard_dir: Path) -> dict:
    """B) Validate fixtures against contract schemas."""
    verdict = "PASS"
    results = []
    violations = []

    fixtures_dir = shard_dir / "conformance" / "fixtures"
    contracts_dir = shard_dir / "contracts"

    if not fixtures_dir.is_dir():
        return {"verdict": "FAIL", "results": [], "violations": ["no conformance/fixtures/ directory"]}

    if not contracts_dir.is_dir():
        return {"verdict": "FAIL", "results": [], "violations": ["no contracts/ directory"]}

    # Load all schemas
    schemas = {}
    for sp in sorted(contracts_dir.glob("*.schema.json")):
        schema = parse_json_schema(sp)
        if schema:
            schemas[sp.stem] = schema

    if not schemas:
        return {"verdict": "FAIL", "results": [], "violations": ["no valid schemas found"]}

    # For each fixture, validate against all schemas
    required_fixtures = ["valid.json", "invalid_pii.json", "invalid_format.json"]
    found_fixtures = sorted(f.name for f in fixtures_dir.glob("*.json"))

    for req in required_fixtures:
        if req not in found_fixtures:
            violations.append(f"missing fixture: {req}")
            verdict = "FAIL"

    for fixture_file in sorted(fixtures_dir.glob("*.json")):
        try:
            instance = json.loads(fixture_file.read_text(encoding="utf-8"))
        except Exception as e:
            violations.append(f"{fixture_file.name}: not JSON-parseable: {e}")
            verdict = "FAIL"
            continue

        is_valid_fixture = fixture_file.name.startswith("valid")
        expected = "PASS" if is_valid_fixture else "FAIL"

        # Validate against each schema
        for schema_name, schema in schemas.items():
            validator = jsonschema.Draft202012Validator(schema)
            errors = list(validator.iter_errors(instance))
            actual = "PASS" if not errors else "FAIL"

            results.append({
                "file": fixture_file.name,
                "schema": schema_name,
                "expected": expected,
                "actual": actual,
            })

            if actual != expected:
                violations.append(
                    f"{fixture_file.name} vs {schema_name}: expected {expected}, got {actual}"
                )
                verdict = "FAIL"

    return {"verdict": verdict, "results": results, "violations": violations}


def run_conformance(root_name: str, shard_name: str) -> dict:
    """Run full conformance for one shard."""
    shard_dir = REPO_ROOT / root_name / "shards" / shard_name

    if not shard_dir.is_dir():
        return {
            "shard": shard_name,
            "root": root_name,
            "verdict": "ERROR",
            "checks": {},
            "errors": [f"shard directory not found: {shard_dir}"],
            "violations": [],
        }

    structure = check_structure(shard_dir)
    schema_val = check_schema_validation(shard_dir)
    fixtures = check_fixtures(shard_dir)

    all_violations = (
        structure.get("violations", [])
        + schema_val.get("violations", [])
        + fixtures.get("violations", [])
    )

    overall = "PASS"
    if any(c["verdict"] != "PASS" for c in [structure, schema_val, fixtures]):
        overall = "FAIL"

    return {
        "shard": shard_name,
        "root": root_name,
        "verdict": overall,
        "checks": {
            "structure": structure,
            "schema_validation": schema_val,
            "fixtures": fixtures,
        },
        "errors": [],
        "violations": all_violations,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Shard Conformance Gate (structure + schema + fixtures)")
    parser.add_argument("--root", type=str, required=True, help="Root name (e.g. 03_core)")
    parser.add_argument("--shard", type=str, help="Shard name (e.g. 01_identitaet_personen)")
    parser.add_argument("--all-shards", action="store_true", help="Check all shards in root")
    parser.add_argument("--report", type=str, help="Write JSON report to path")
    args = parser.parse_args()

    if args.root not in ROOTS_24:
        print(f"ERROR: Unknown root '{args.root}'")
        return 2

    root_path = REPO_ROOT / args.root
    if not root_path.is_dir():
        print(f"ERROR: Root directory not found: {root_path}")
        return 2

    if not args.shard and not args.all_shards:
        print("ERROR: Specify --shard <name> or --all-shards")
        return 2

    # Determine shards
    if args.all_shards:
        shard_dirs = find_shards(root_path)
        shard_names = [d.name for d in shard_dirs]
    else:
        shard_dir = root_path / "shards" / args.shard
        if not shard_dir.is_dir():
            print(f"ERROR: Shard directory not found: {shard_dir}")
            return 2
        shard_names = [args.shard]

    # Run conformance
    results = []
    overall_pass = True
    for shard_name in shard_names:
        report = run_conformance(args.root, shard_name)
        results.append(report)

        status = report["verdict"]
        print(f"{status}: {args.root}/shards/{shard_name}")
        if report["violations"]:
            for v in report["violations"]:
                print(f"  - {v}")
        if status != "PASS":
            overall_pass = False

    # Summary
    passed = sum(1 for r in results if r["verdict"] == "PASS")
    failed = sum(1 for r in results if r["verdict"] == "FAIL")
    errors = sum(1 for r in results if r["verdict"] == "ERROR")
    print(f"\nSummary: {passed} passed, {failed} failed, {errors} errors")

    # Write report
    if args.report:
        report_data = results[0] if len(results) == 1 else {"shards": results}
        Path(args.report).write_text(
            json.dumps(report_data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"Report written to: {args.report}")

    if not overall_pass:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

**Step 4: Run tests and verify PASS**

Run: `cd "C:\Users\bibel\Documents\Github\SSID" && python -m pytest 11_test_simulation/tests_compliance/test_shard_conformance_gate.py -v`
Expected: All PASS (requires Task 4 fixtures + manifest.yaml to be present)

Note: If tests fail because manifest.yaml doesn't exist yet at shard level, run `python 12_tooling/cli/shard_manifest_build.py --root 03_core --apply` first.

**Step 5: Commit**

```bash
git add 12_tooling/cli/shard_conformance_gate.py 11_test_simulation/tests_compliance/test_shard_conformance_gate.py
git commit -m "feat(ts014): add shard_conformance_gate.py (structure + schema + fixtures)"
```

---

### Task 6: Create pytest conformance modules per pilot shard

**Files:**
- Create: `03_core/shards/01_identitaet_personen/conformance/test_conformance_identity.py`
- Create: `03_core/shards/02_dokumente_nachweise/conformance/test_conformance_document.py`

**Step 1: Create shard 01 pytest module**

```python
#!/usr/bin/env python3
"""Conformance tests for shard 01_identitaet_personen (identity_proof)."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

SHARD_DIR = Path(__file__).resolve().parent.parent
SCHEMA_PATH = SHARD_DIR / "contracts" / "identity_proof.schema.json"
FIXTURES_DIR = SHARD_DIR / "conformance" / "fixtures"


@pytest.fixture
def schema():
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def validator(schema):
    return jsonschema.Draft202012Validator(schema)


def test_schema_is_valid(schema):
    jsonschema.Draft202012Validator.check_schema(schema)


def test_valid_fixture_passes(validator):
    instance = json.loads((FIXTURES_DIR / "valid.json").read_text(encoding="utf-8"))
    validator.validate(instance)


def test_invalid_pii_fails(validator):
    instance = json.loads((FIXTURES_DIR / "invalid_pii.json").read_text(encoding="utf-8"))
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(instance)


def test_invalid_format_fails(validator):
    instance = json.loads((FIXTURES_DIR / "invalid_format.json").read_text(encoding="utf-8"))
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(instance)
```

**Step 2: Create shard 02 pytest module**

```python
#!/usr/bin/env python3
"""Conformance tests for shard 02_dokumente_nachweise (document_proof)."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

SHARD_DIR = Path(__file__).resolve().parent.parent
SCHEMA_PATH = SHARD_DIR / "contracts" / "document_proof.schema.json"
FIXTURES_DIR = SHARD_DIR / "conformance" / "fixtures"


@pytest.fixture
def schema():
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def validator(schema):
    return jsonschema.Draft202012Validator(schema)


def test_schema_is_valid(schema):
    jsonschema.Draft202012Validator.check_schema(schema)


def test_valid_fixture_passes(validator):
    instance = json.loads((FIXTURES_DIR / "valid.json").read_text(encoding="utf-8"))
    validator.validate(instance)


def test_invalid_pii_fails(validator):
    instance = json.loads((FIXTURES_DIR / "invalid_pii.json").read_text(encoding="utf-8"))
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(instance)


def test_invalid_format_fails(validator):
    instance = json.loads((FIXTURES_DIR / "invalid_format.json").read_text(encoding="utf-8"))
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(instance)
```

**Step 3: Run both pytest modules**

Run: `cd "C:\Users\bibel\Documents\Github\SSID" && python -m pytest 03_core/shards/01_identitaet_personen/conformance/ 03_core/shards/02_dokumente_nachweise/conformance/ -v`
Expected: All 8 tests PASS

**Step 4: Commit**

```bash
git add 03_core/shards/01_identitaet_personen/conformance/test_conformance_identity.py 03_core/shards/02_dokumente_nachweise/conformance/test_conformance_document.py
git commit -m "test(ts014): add per-shard pytest conformance modules"
```

---

### Task 7: Update `run_all_gates.py` (add conformance gate)

**Files:**
- Modify: `12_tooling/cli/run_all_gates.py`

**Step 1: Add conformance gate constant and function**

Add after SHARD_GATE line:
```python
CONFORMANCE_GATE = PROJECT_ROOT / "12_tooling" / "cli" / "shard_conformance_gate.py"
```

Add function after `run_shard_gate()`:
```python
def run_conformance_gate() -> bool:
    """Gate: conformance check for pilot shards."""
    print("INFO: [GATE] Running Shard Conformance Gate...")
    if not CONFORMANCE_GATE.exists():
        print(f"ERROR: Conformance gate missing: {CONFORMANCE_GATE}")
        return False
    # Run for each pilot shard
    for shard in ["01_identitaet_personen", "02_dokumente_nachweise"]:
        proc = _run(
            [sys.executable, str(CONFORMANCE_GATE), "--root", "03_core", "--shard", shard],
            f"Conformance Gate ({shard})",
        )
        if proc.returncode != 0:
            return False
    print("INFO: [GATE] Shard Conformance Gate PASSED.")
    return True
```

**Step 2: Insert into gate chain**

In main(), after the shard gate block, add:
```python
    if not run_conformance_gate():
        print("\nERROR: Gate chain failed at Conformance Gate.")
        return 1
```

Update the chain description:
```python
    print("--- Running Full Gate Chain: Policy -> SoT -> Shard -> Conformance -> QA ---")
```

**Step 3: Commit**

```bash
git add 12_tooling/cli/run_all_gates.py
git commit -m "feat(ts014): integrate conformance gate into run_all_gates.py chain"
```

---

### Task 8: Generate shard-level manifests for pilot shards + full verification

**Step 1: Generate manifests for 03_core pilot shards**

```bash
cd "C:\Users\bibel\Documents\Github\SSID"
python 12_tooling/cli/shard_manifest_build.py --root 03_core --apply
```

Expected: CREATED for shards that lack shard-level manifest.yaml

**Step 2: Run conformance gate for both pilots**

```bash
python 12_tooling/cli/shard_conformance_gate.py --root 03_core --shard 01_identitaet_personen
python 12_tooling/cli/shard_conformance_gate.py --root 03_core --shard 02_dokumente_nachweise
```

Expected: PASS for both

**Step 3: Run all pytest conformance tests**

```bash
python -m pytest 03_core/shards/01_identitaet_personen/conformance/ 03_core/shards/02_dokumente_nachweise/conformance/ -v
```

Expected: All 8 tests PASS

**Step 4: Run full gate chain**

```bash
python 12_tooling/cli/run_all_gates.py
```

Expected: Full chain PASS (Policy -> SoT -> Shard -> Conformance -> QA)

Note: Some gates may fail if dependencies (OPA, etc.) aren't available locally. At minimum, shard + conformance gates must PASS.

**Step 5: Commit generated manifests**

```bash
git add 03_core/shards/*/manifest.yaml
git commit -m "chore(ts013): generate shard-level manifest.yaml for 03_core shards"
```

---

### Task 9: Push + PR

**Step 1: Push branch**

```bash
git push -u origin feat/ts013-ts014-manifest-conformance
```

**Step 2: Create PR**

```bash
gh pr create --title "feat(ts013+ts014): manifest generator + conformance gate" --body "$(cat <<'EOF'
## Summary
- **TS013**: Rewrote `shard_manifest_build.py` — parametric (`--root`/`--all`), shard-level output, `--apply`/`--dry-run`, JSON report
- **TS014**: New `shard_conformance_gate.py` — structure + schema + fixture validation, JSON report, exit 0/1/2
- Shared lib `_lib/shards.py` for deterministic scan/parse/validate
- Conformance fixtures (valid + invalid_pii + invalid_format) per pilot shard
- Per-shard pytest conformance modules
- Gate chain extended: Policy → SoT → Shard → **Conformance** → QA

## PASS Criteria
- [x] `shard_conformance_gate.py` PASS for both pilot shards
- [x] `python -m pytest` PASS (all conformance tests)
- [x] `run_all_gates.py` PASS (full chain)
- [x] Reports contain only lists/counts/PASS/FAIL, no scores

## Test plan
- [ ] Run `shard_manifest_build.py --root 03_core --dry-run` (no writes)
- [ ] Run `shard_manifest_build.py --root 03_core --apply` (creates manifests)
- [ ] Run `shard_conformance_gate.py --root 03_core --shard 01_identitaet_personen`
- [ ] Run `shard_conformance_gate.py --root 03_core --shard 02_dokumente_nachweise`
- [ ] Run pytest conformance tests
- [ ] Verify no scores/percentages in any output

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```
