# TS013 + TS014 Design: Shard Manifest Generator (Global) + Pilot Conformance Gate

**Date:** 2026-03-02
**Status:** Approved
**Approach:** B — Shared Lib + Separate CLIs

## Context

TS012 delivered the Local Orchestrator MVP (SSID-orchestrator repo).
TS013+TS014 are Hybrid-C shard infrastructure tasks in the SSID repo:

- **TS013**: Generate `manifest.yaml` per shard from existing `chart.yaml` — parametric, all 24 roots
- **TS014**: Full Conformance Gate for pilot shards (01_identitaet_personen, 02_dokumente_nachweise)

## Current State

| Asset | Count | Notes |
|---|---|---|
| chart.yaml | 384 | 24 roots x 16 shards |
| manifest.yaml (implementations/) | 753 | _stub + python + others |
| manifest.yaml (shard-level) | 0 | Target of TS013 |
| Contract schemas (pilot) | 2 | identity_proof + document_proof |
| Conformance tests | 0 | Target of TS014 |

Existing tools:
- `shard_manifest_build.py` — hardcoded to 03_core only, outputs to implementations/generated/
- `shard_gate_chart_manifest.py` — 03_core only, presence check only
- `run_all_gates.py` — already calls shard_gate in chain

## Architecture

```
12_tooling/cli/
  _lib/
    __init__.py
    shards.py                    # Shared: scan, parse, validate, write
  shard_manifest_build.py        # TS013: Rewrite (parametric, shard-level output)
  shard_gate_chart_manifest.py   # TS013: Update (recognize shard-level manifest)
  shard_conformance_gate.py      # TS014: New (structure+schema+fixtures+report)
  run_all_gates.py               # Update: + conformance gate in chain

03_core/shards/<pilot>/
  chart.yaml                     # Existing
  manifest.yaml                  # TS013: Generated (shard-level, next to chart.yaml)
  contracts/*.schema.json        # Existing
  conformance/
    fixtures/valid.json           # TS014: New
    fixtures/invalid_pii.json     # TS014: New
    fixtures/invalid_format.json  # TS014: New
    test_conformance_*.py         # TS014: New
```

## _lib/shards.py — Shared Primitives

| Function | Purpose |
|---|---|
| `ROOTS_24: list[str]` | Canonical 24 root names |
| `find_roots(repo_root) -> list[Path]` | All root directories (sorted) |
| `find_shards(root_path) -> list[Path]` | Shard dirs under `<root>/shards/` (sorted) |
| `parse_yaml(path) -> dict or None` | Safe YAML parse (UTF-8), None on error |
| `parse_json_schema(path) -> dict or None` | Safe JSON parse + Draft-2020-12 structure check |
| `validate_manifest_fields(data) -> list[str]` | Required fields: shard_id, root_id, version, implementation_stack, contracts, conformance, policies |
| `check_pii_keys(schema) -> list[str]` | Deny pattern on property keys |
| `write_yaml(path, data) -> bool` | UTF-8/LF, no-overwrite (returns False if exists) |

Constraints:
- Deterministic order (sorted paths)
- UTF-8/LF on write
- No-overwrite strict
- No score output (PASS/FAIL + lists/counts only)

## TS013: shard_manifest_build.py

### CLI Contract

```
python shard_manifest_build.py --root 03_core --dry-run     # preview
python shard_manifest_build.py --root 03_core --apply        # write
python shard_manifest_build.py --all --apply                 # all 24 roots
python shard_manifest_build.py --report report.json --all --dry-run
```

- No `--root` and no `--all` = help/dry-run (safe default)
- `--apply` required to write

### Output Location

`<root>/shards/<shard>/manifest.yaml` (next to chart.yaml, NOT in implementations/)

### No-Overwrite Rules

- If `manifest.yaml` exists at shard level -> SKIP
- If only `_stub/manifest.yaml` exists in implementations/ -> create NEW shard-level manifest, _stub untouched

### Generated manifest.yaml Schema

```yaml
shard_id: "01_identitaet_personen"
root_id: "03_core"
version: "1.0.0"                    # from chart.yaml
implementation_stack: "generated"
contracts:
  - "contracts/identity_proof.schema.json"
conformance: []
policies:
  - ref: "hash_only"
  - ref: "non_custodial"
```

Fields derived from chart.yaml: version, policies (from policies[].id).
Fields derived from filesystem: shard_id (dir name), root_id (parent dir name), contracts (glob contracts/*.schema.json).

### shard_gate_chart_manifest.py Update

- `check_shard()` recognizes shard-level `manifest.yaml` (next to chart.yaml)
- Falls back to `implementations/*/manifest.yaml` for backward compat
- Advisory for non-pilot shards, enforced for pilot shards (01, 02)

## TS014: shard_conformance_gate.py

### CLI Contract

```
python shard_conformance_gate.py --root 03_core --shard 01_identitaet_personen
python shard_conformance_gate.py --root 03_core --all-shards
python shard_conformance_gate.py --root 03_core --shard 01_identitaet_personen --report report.json
```

Exit codes: 0=PASS, 1=FAIL, 2=ERROR (I/O)

### Validations

**A) Structure Conformance (MUST):**
- chart.yaml exists + YAML-parseable
- manifest.yaml exists + YAML-parseable + required fields (shard_id, root_id, version, implementation_stack, contracts, conformance, policies)
- contracts/*.schema.json exist + UTF-8 + JSON-parseable
- JSON Schema structurally valid (Draft 2020-12)
- No PII keys in schema properties (deny: name, birth, address, doc_number, email, url)

**B) Schema + Fixture Tests (MUST):**
- Per shard: min 3 fixtures in conformance/fixtures/
- valid.json -> schema validation PASS
- invalid_pii.json -> schema validation FAIL
- invalid_format.json -> schema validation FAIL
- Validation via jsonschema (Python, Draft 2020-12)

**C) Report (JSON):**

```json
{
  "shard": "01_identitaet_personen",
  "root": "03_core",
  "verdict": "PASS",
  "checks": {
    "structure": {"verdict": "PASS", "checked_files": ["chart.yaml", "manifest.yaml", "contracts/identity_proof.schema.json"]},
    "schema_validation": {"verdict": "PASS", "checked_files": ["contracts/identity_proof.schema.json"]},
    "fixtures": {"verdict": "PASS", "results": [
      {"file": "valid.json", "expected": "PASS", "actual": "PASS"},
      {"file": "invalid_pii.json", "expected": "FAIL", "actual": "FAIL"},
      {"file": "invalid_format.json", "expected": "FAIL", "actual": "FAIL"}
    ]}
  },
  "errors": [],
  "violations": []
}
```

### Fixtures

**Shard 01 (identity_proof):**
- valid.json: correct proof_hash (0x + 64 hex), sha256, person, RFC3339 Zulu, optional issuer_id
- invalid_pii.json: adds name/email fields -> FAIL (additionalProperties: false)
- invalid_format.json: hash without 0x prefix, invalid enum, wrong timestamp format

**Shard 02 (document_proof):**
- valid.json: correct doc_hash (0x + 64 hex), sha256, id_document, RFC3339 Zulu
- invalid_pii.json: adds address/doc_number fields -> FAIL
- invalid_format.json: hash without 0x, invalid doc_type, wrong timestamp

### Pytest Modules

- `03_core/shards/01_.../conformance/test_conformance_identity.py`
- `03_core/shards/02_.../conformance/test_conformance_document.py`

Each loads fixtures, validates against schema, asserts PASS/FAIL expectations.

## Integration: run_all_gates.py

New constant:
```python
CONFORMANCE_GATE = PROJECT_ROOT / "12_tooling" / "cli" / "shard_conformance_gate.py"
```

New function `run_conformance_gate()` calls gate for pilot shards.

Gate chain becomes: Policy -> SoT -> Shard Gate -> **Conformance Gate** -> QA

## Dependencies

- `jsonschema` (Python, for Draft 2020-12 validation) — add to requirements if missing
- `PyYAML` — already present

## PASS Criteria

- shard_conformance_gate.py: PASS for both pilot shards
- python -m pytest -q: PASS (conformance tests)
- run_all_gates.py: PASS (full chain)
- Reports contain only lists/counts/PASS/FAIL, no scores
