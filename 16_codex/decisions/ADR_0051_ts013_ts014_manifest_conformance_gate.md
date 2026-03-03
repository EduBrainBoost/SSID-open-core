# ADR-0051: TS013+TS014 Manifest Generator and Conformance Gate

Date: 2026-03-02
Status: Accepted
Decider: EduBrainBoost

## Context
Hybrid-C architecture requires:
1. Parametric manifest generation from chart.yaml metadata (TS013)
2. Pilot contract schemas with conformance validation (TS014)
3. PII denial enforcement in all contract schemas
4. Integration into the existing gate chain (run_all_gates.py)

Previously, shards had chart.yaml but no manifest.yaml and no contract validation.

## Decision
Add 3 new CLI tools and 1 shared library:
- `12_tooling/cli/shard_manifest_build.py` — parametric manifest generator (--root/--all, default dry-run, --apply to write)
- `12_tooling/cli/shard_gate_chart_manifest.py` — chart+manifest presence gate (--pilot for shards 01/02)
- `12_tooling/cli/shard_conformance_gate.py` — validates contracts, schemas, PII denial, and fixtures (exit 0/1/2)
- `12_tooling/cli/_lib/shards.py` — shared primitives (ROOTS_24, SHARDS_16, YAML/JSON helpers)

Pilot contracts (JSON Schema Draft 2020-12):
- `03_core/shards/01_identitaet_personen/contracts/identity_proof.schema.json`
- `03_core/shards/02_dokumente_nachweise/contracts/document_proof.schema.json`

Each pilot shard gets valid + invalid conformance fixtures and a generated manifest.yaml.

Gate chain updated: Policy -> SoT -> Shard Gate -> Conformance Gate -> QA.

## Consequences
- Manifest generation is additive-only (never overwrites existing manifest.yaml)
- PII denial blocks SSN, passport, DOB, name, email, phone, address, credit card, national ID, biometric, geolocation, IP address patterns in schema property keys
- URL denial blocks http(s) URLs in schema default/const/enum values
- Conformance gate enforces valid fixtures PASS and invalid fixtures FAIL validation
- No scores (PASS/FAIL + findings only)

## Guards
ROOT-24-LOCK: unchanged | SAFE-FIX: additive only | PR-only
