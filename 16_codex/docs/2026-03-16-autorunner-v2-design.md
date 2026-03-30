# SSID AutoRunner V2 — Vollständiges Design-Dokument

**Version:** 1.0.0
**Datum:** 2026-03-16
**Status:** DESIGN — Warten auf GO für Implementierung
**SoT-Basis:** master_v1.1.1, WORKFLOW.md, AGENTS.md, sot_contract.yaml v4.1.0
**Ansatz:** C — Hybrid Layered
**Scope:** 10 neue AutoRunner (AR-01 bis AR-10)

---

## Architektur-Überblick (Ansatz C)

```
GitHub Action (deterministischer Trigger)
    │
    ├── Phase 1: Deterministic Checks (bash/Python, kein AI)
    │   └── repo_scan.json erzeugen (OPA-Input)
    │
    ├── Phase 2: EMS Gate-Runner HTTP-Call
    │   ├── Gate: policy → sot → qa → duplicate-guard
    │   ├── [optional] Agent Worker (worktree-isoliert, patch-only)
    │   └── Evidence: hash-only JSONL → 02_audit_logging/agent_runs/<run_id>/
    │
    └── Phase 3: Result
        ├── PASS → Orchestrator appliziert Patch / erstellt PR
        └── FAIL → Action exit ≠ 0 → PR blockiert / Cron-Alert
```

**Kernregeln (aus AGENTS.md + WORKFLOW.md):**
- Worker: nur in `.ssid_sandbox/<run_id>/<task_id>/` (keine direkten Repo-Writes)
- Gates: nur echte Checks (`policy → sot → qa`), kein Simulation
- Integrator: appliziert nur nach PASS aller Gates
- Evidence: minimal, hash-only, in `02_audit_logging/agent_runs/`
- Cleanup: `.ssid_sandbox`-Artefakte nach Abschluss entfernen

---

## Gemeinsames Interface

### OPA-Input: repo_scan.json (einzige gültige Quelle)

Per SoT v1.1.1 §7: alle OPA/EMS-Checks verwenden ausschließlich
`24_meta_orchestration/registry/generated/repo_scan.json`.

**Erzeugung (jede Action die OPA nutzt):**
```yaml
- name: Generate repo_scan.json
  run: |
    python 24_meta_orchestration/scripts/generate_repo_scan.py \
      --repo-root . \
      --commit-sha "${{ github.sha }}" \
      --out 24_meta_orchestration/registry/generated/repo_scan.json
```

**Schema (repo_scan.json):**
```json
{
  "scan_ts": "ISO8601",
  "commit_sha": "40-char hex",
  "repo": "SSID",
  "roots": [
    { "id": "01_ai_layer", "path": "01_ai_layer", "exists": true }
  ],
  "files": [
    { "path": "relative/path", "ext": ".py", "size_bytes": 1234,
      "sha256": "hex", "root": "01_ai_layer" }
  ],
  "forbidden_extensions_found": [],
  "shard_counts": { "01_ai_layer": 16, "02_audit_logging": 16 },
  "chart_yaml_present": { "01_ai_layer/shards/01_identitaet_personen": true },
  "incident_response_plans": {
    "01_ai_layer": { "exists": false, "path": "01_ai_layer/docs/incident_response_plan.md" }
  },
  "sanctions_sources": {
    "last_updated": "ISO8601",
    "age_hours": 12,
    "max_age_hours": 24
  }
}
```

### EMS Gate-Runner: Gemeinsames Input-Payload-Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["run_id", "autorunner_id", "trigger", "repo", "commit_sha"],
  "properties": {
    "run_id":         { "type": "string", "format": "uuid" },
    "autorunner_id":  { "type": "string", "enum":
                        ["AR-01","AR-02","AR-03","AR-04","AR-05",
                         "AR-06","AR-07","AR-08","AR-09","AR-10"] },
    "trigger":        { "type": "string", "enum": ["push","cron","pr","manual"] },
    "repo":           { "type": "string" },
    "branch":         { "type": "string" },
    "commit_sha":     { "type": "string", "pattern": "^[0-9a-f]{40}$" },
    "scope_lock": {
      "type": "object",
      "properties": {
        "allowed_paths":   { "type": "array", "items": { "type": "string" } },
        "forbidden_paths": { "type": "array", "items": { "type": "string" } }
      }
    },
    "agent_task": {
      "type": "object",
      "properties": {
        "agent_id":   { "type": "string" },
        "model":      { "type": "string", "enum": ["opus","sonnet","haiku"] },
        "max_tokens": { "type": "integer", "default": 4096 }
      }
    },
    "opa_input_path": { "type": "string",
      "description": "Pflicht: 24_meta_orchestration/registry/generated/repo_scan.json" },
    "context":        { "type": "object" }
  }
}
```

### Output-Artefakte (immer in `02_audit_logging/agent_runs/<run_id>/`)

```
manifest.json         Hash-only Ledger: {run_id, autorunner_id, status, ts,
                       sha256_of_evidence, gates_passed, gates_failed}
evidence.jsonl        WORM-Append: eine Zeile pro Gate-Check-Ergebnis
manifest.json.sha256  SHA256-Prüfsumme von manifest.json
patch.diff            (optional) nur für Worker-Runs die Änderungen produzieren
```

**manifest.json Schema:**
```json
{
  "run_id": "uuid",
  "autorunner_id": "AR-01",
  "trigger": "push",
  "repo": "SSID",
  "commit_sha": "abc...",
  "status": "PASS|FAIL_*|ERROR",
  "ts_start": "ISO8601",
  "ts_end": "ISO8601",
  "gates_passed": ["policy", "sot"],
  "gates_failed": [],
  "sha256_of_evidence": "hex",
  "agent_used": false,
  "evidence_lines": 42
}
```

### Status-Codes

| Code | Bedeutung |
|------|-----------|
| `PASS` | Alle Gates grün |
| `FAIL_POLICY` | Policy-Gate: OPA/Semgrep/PII verletzt |
| `FAIL_SOT` | SoT-Konformität (SOT_AGENT_001-036) verletzt |
| `FAIL_QA` | QA-Gate (Tests, Schemathesis) failed |
| `FAIL_DUPLICATE` | Duplicate-Guard ausgelöst |
| `FAIL_SCOPE` | Agent hat Scope-Verletzung versucht |
| `FAIL_FORBIDDEN` | Verbotene Extension oder Secret gefunden |
| `FAIL_FRESHNESS` | Datenquelle älter als erlaubte max_age |
| `FAIL_DORA` | DORA: incident_response_plan.md fehlt |
| `FAIL_SHARD` | Shard-Completeness < 384 chart.yaml |
| `ERROR` | Interner EMS-Fehler (retry-fähig) |

---

## AR-01: pii_scanner

**SoT-Regel:** master_v1.1.1 §1 (Non-Custodial), chart.yaml `constraints.pii_storage: "forbidden"`
**Zweck:** Verhindert PII-Storage in Code/Configs/Logs

### 1. Trigger + Repo-Scope
```yaml
on:
  push:
    branches: ['**']
  pull_request:
    branches: [main, develop]
repos: [SSID, SSID-EMS, SSID-open-core]
changed_files_only: true
```

### 2. Deterministische Checks (GitHub Action)
```bash
# Schritt 1: Semgrep mit SSID-PII-Ruleset
semgrep \
  --config 23_compliance/rules/pii_semgrep.yaml \
  --config p/python \
  --error \
  --json \
  --output /tmp/semgrep_results.json \
  $(git diff --name-only HEAD~1)

# Schritt 2: Bandit (Python-spezifisch)
bandit -r . -ll --format json -o /tmp/bandit_results.json || true

# Schritt 3: Regex-Scan auf PII-Patterns in geänderten Dateien
python 23_compliance/scripts/pii_regex_scan.py \
  --files "$(git diff --name-only HEAD~1)" \
  --patterns 23_compliance/rules/pii_patterns.yaml \
  --out /tmp/pii_regex_results.json

# Schritt 4: repo_scan.json erzeugen
python 24_meta_orchestration/scripts/generate_repo_scan.py \
  --repo-root . --commit-sha "$GITHUB_SHA" \
  --out 24_meta_orchestration/registry/generated/repo_scan.json
```

**PII-Patterns (23_compliance/rules/pii_patterns.yaml) enthält:**
- Email-Adressen: `[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}`
- IBAN: `[A-Z]{2}[0-9]{2}[A-Z0-9]{4}[0-9]{7}([A-Z0-9]?){0,16}`
- Deutsche Personalausweisnummer
- Telefonnummern
- IP-Adressen (außer 0.0.0.0/127.0.0.1/::1)

### 3. EMS Gate-Runner Interface
```json
{
  "autorunner_id": "AR-01",
  "trigger": "push",
  "scope_lock": {
    "allowed_paths": ["**/*.py","**/*.ts","**/*.sol","**/*.yaml","**/*.json"],
    "forbidden_paths": ["02_audit_logging/storage/worm/**",".git/**","node_modules/**"]
  },
  "agent_task": {
    "agent_id": "05_security_compliance",
    "model": "opus",
    "max_tokens": 2048
  },
  "opa_input_path": "24_meta_orchestration/registry/generated/repo_scan.json",
  "context": {
    "semgrep_results_path": "/tmp/semgrep_results.json",
    "bandit_results_path": "/tmp/bandit_results.json",
    "pii_regex_results_path": "/tmp/pii_regex_results.json",
    "changed_files": []
  }
}
```

**evidence.jsonl Format (ein Eintrag pro Datei):**
```jsonl
{"ts":"ISO8601","file":"path/to/file.py","sha256":"hex","check":"semgrep","result":"PASS","findings":0}
{"ts":"ISO8601","file":"path/to/service.py","sha256":"hex","check":"pii_regex","result":"FAIL","findings":1,"pattern":"email"}
```

### 4. Claude-Agent-Einsatz
**Agent:** Agent-SEC (05_security_compliance) — **Opus**
**Wann:** NUR wenn Semgrep uncertain/borderline Matches meldet (confidence < 0.8)
**Scope-Lock:** Read-only auf geflaggte Dateien — kein Write
**Task:** Klassifikation True/False Positive; Output → evidence.jsonl
**Kein Patch:** Gate-only, keine Code-Änderungen durch Agent

### 5. WORKFLOW.md Step-Mapping
1. **Plan:** task_spec mit `allowed_paths=[geänderte Dateien]`
2. **Patch:** keiner (read-only Gate)
3. **Gates:** `semgrep(policy)` → `pii_regex(policy)` → `bandit(qa)`
4. **Guard:** duplicate-guard auf evidence JSONL (kein Doppel-Scan)
5. **Integrate:** N/A — Gate-only
6. **Evidence:** `02_audit_logging/agent_runs/<run_id>/manifest.json` + `evidence.jsonl`
7. **Cleanup:** `/tmp/semgrep_results.json` etc. löschen

### 6. Concurrency
- Max 3 parallele Worker (je geänderte Datei-Batch: ≤100 Dateien)
- Timeout: 15 min
- Isolation: jeder Batch in eigenem `.ssid_sandbox/<run_id>/batch_<n>/`

### 7. Tests
```
tests/autorunners/test_ar01_pii_scanner.py
  - test_clean_file_passes()         # Datei ohne PII → PASS
  - test_email_in_code_fails()       # E-Mail-Adresse im Code → FAIL_POLICY
  - test_hash_only_passes()          # SHA3-256 Hash → PASS (kein PII)
  - test_semgrep_false_positive()    # Agent-Klassifikation testen
  - test_evidence_jsonl_format()     # WORM-Ausgabe validieren

# Lokale Simulation:
bash scripts/autorunners/ar01_simulate.sh \
  --files "src/identity.py" \
  --dry-run
```

---

## AR-02: contract_tests

**SoT-Regel:** master §3 (Contract-First), SOT_AGENT_001-036 Konformanz
**Zweck:** OpenAPI-Contracts müssen gegen Schemathesis bestehen bevor Merge

### 1. Trigger + Repo-Scope
```yaml
on:
  push:
    paths: ['**/contracts/**/*.openapi.yaml', '**/contracts/schemas/**']
  pull_request:
    branches: [main]
repos: [SSID]
```

### 2. Deterministische Checks (GitHub Action)
```bash
# Schritt 1: Alle Contract-Dateien finden
python 12_tooling/scripts/find_contracts.py \
  --repo-root . \
  --out /tmp/contract_list.json

# Schritt 2: Schema-Validierung
python -m jsonschema validate \
  --instance /tmp/contract_list.json \
  --schema 16_codex/contracts/dispatcher/task_spec.schema.json

# Schritt 3: Schemathesis (nur geänderte Contracts)
for contract in $(jq -r '.changed[]' /tmp/contract_list.json); do
  schemathesis run "$contract" \
    --validate-schema=true \
    --checks all \
    --report /tmp/schemathesis_$(basename $contract).json
done

# Schritt 4: SOT-Konformanz-Check
python 24_meta_orchestration/scripts/sot_contract_check.py \
  --rules 16_codex/contracts/sot/sot_contract.yaml \
  --repo-scan 24_meta_orchestration/registry/generated/repo_scan.json \
  --out /tmp/sot_check_results.json
```

### 3. EMS Gate-Runner Interface
```json
{
  "autorunner_id": "AR-02",
  "scope_lock": {
    "allowed_paths": ["**/contracts/**","**/schemas/**","16_codex/contracts/**"],
    "forbidden_paths": ["02_audit_logging/storage/worm/**"]
  },
  "agent_task": {
    "agent_id": "04_gate_runner_auditor",
    "model": "sonnet",
    "max_tokens": 4096
  },
  "opa_input_path": "24_meta_orchestration/registry/generated/repo_scan.json",
  "context": {
    "contract_list_path": "/tmp/contract_list.json",
    "schemathesis_results": "/tmp/schemathesis_*.json",
    "sot_check_results": "/tmp/sot_check_results.json"
  }
}
```

**Status:** PASS | FAIL_QA (Schemathesis) | FAIL_SOT (SOT_AGENT Regel)

### 4. Claude-Agent-Einsatz
**Agent:** Agent-AUD (04_gate_runner_auditor) — **Sonnet**
**Wann:** NUR wenn Schemathesis Fehler meldet die manuell klassifiziert werden müssen
**Zusätzlich:** Agent-API (24_api_specialist) — **Sonnet** bei Semantic-Contract-Fragen
**Scope-Lock:** Read-only auf geänderte Contract-Dateien
**Output:** Klassifikation + Gap-Report → evidence.jsonl

### 5. WORKFLOW.md Step-Mapping
1. **Plan:** scope = geänderte `*.openapi.yaml` und `*.schema.json`
2. **Patch:** keiner (Gate-only)
3. **Gates:** `schemathesis(qa)` → `sot_contract_check(sot)` → `schema_validation(policy)`
4. **Guard:** Duplicate-Guard auf Schemathesis-Report-Hash
5. **Integrate:** N/A
6. **Evidence:** manifest + evidence.jsonl mit je Contract-Hash und Testergebnis
7. **Cleanup:** `/tmp/schemathesis_*` löschen

### 6. Concurrency
- 1 Worker pro geändertem Contract-File
- Max 5 parallel
- Timeout: 20 min

### 7. Tests
```
tests/autorunners/test_ar02_contract_tests.py
  - test_valid_openapi_passes()
  - test_missing_required_field_fails()
  - test_sot_agent_001_dispatcher_single_entry()
  - test_sot_rules_36_all_checked()

# Lokal:
bash scripts/autorunners/ar02_simulate.sh --contract 01_ai_layer/shards/01_identitaet_personen/contracts/
```

---

## AR-03: evidence_anchoring

**SoT-Regel:** master §5 (Evidence-Based Compliance), hourly anchoring
**Zweck:** WORM-Hashes stündlich auf Blockchain anchoren

### 1. Trigger + Repo-Scope
```yaml
on:
  schedule:
    - cron: '0 * * * *'   # stündlich
  workflow_dispatch:       # manuell auslösbar
repos: [SSID]
paths_read: ['02_audit_logging/']
```

### 2. Deterministische Checks (GitHub Action)
```bash
# Schritt 1: Neue Evidence-Einträge seit letztem Anchor sammeln
python 02_audit_logging/scripts/collect_unanchored.py \
  --since-last-anchor 02_audit_logging/logs/anchor_state.json \
  --out /tmp/unanchored_entries.json

# Schritt 2: Merkle-Tree berechnen
python 02_audit_logging/scripts/build_merkle_tree.py \
  --input /tmp/unanchored_entries.json \
  --out /tmp/merkle_root.json

# Schritt 3: SHA256-Manifest erzeugen
python 16_codex/archives/test_backups/cron_sha256_manifest.py \
  --entries /tmp/unanchored_entries.json \
  --out /tmp/sha256_manifest.json
```

### 3. EMS Gate-Runner Interface
```json
{
  "autorunner_id": "AR-03",
  "scope_lock": {
    "allowed_paths": ["02_audit_logging/logs/**","02_audit_logging/agent_runs/**"],
    "forbidden_paths": ["02_audit_logging/storage/worm/**"]
  },
  "agent_task": {
    "agent_id": "08_ops_runner",
    "model": "haiku",
    "max_tokens": 1024
  },
  "context": {
    "unanchored_entries": "/tmp/unanchored_entries.json",
    "merkle_root": "/tmp/merkle_root.json",
    "target_chains": ["ethereum", "polygon"],
    "anchor_mode": "dry_run_if_no_entries"
  }
}
```

**evidence.jsonl:**
```jsonl
{"ts":"ISO8601","anchor_root":"merkle_hex","chain":"ethereum","tx_hash":"0x...","entries_anchored":42}
{"ts":"ISO8601","anchor_root":"merkle_hex","chain":"polygon","tx_hash":"0x...","entries_anchored":42}
```

### 4. Claude-Agent-Einsatz
**Agent:** Agent-OPS (08_ops_runner) — **Haiku**
**Wann:** NUR bei Fehler beim Anchor-Prozess (retry-Logik, Chain-Selection)
**Agent-OBS (17_observability_engineer) — Haiku:** für Monitoring-Alerts bei wiederholten Fehlern
**Scope-Lock:** Read-only `02_audit_logging/logs/`; Write nur in `02_audit_logging/logs/anchor_state.json`

### 5. WORKFLOW.md Step-Mapping
1. **Plan:** scope = neue `evidence.jsonl`-Einträge seit letztem Anchor
2. **Patch:** `02_audit_logging/logs/anchor_state.json` updaten
3. **Gates:** `freshness_check(policy)` → `merkle_validate(qa)`
4. **Guard:** verhindert Doppel-Anchoring desselben Merkle-Root
5. **Integrate:** anchor_state.json via PR (oder direkter Commit durch Ops-Runner nach PASS)
6. **Evidence:** Anchor-TX-Hash in evidence.jsonl
7. **Cleanup:** `/tmp/unanchored_*` löschen

### 6. Concurrency
- 1 Worker (sequentiell — Merkle-Root muss konsistent sein)
- Timeout: 5 min
- Bei Fehler: exponentielles Retry (3×), dann Alert an Agent-OBS

### 7. Tests
```
tests/autorunners/test_ar03_evidence_anchoring.py
  - test_empty_queue_skips_anchoring()
  - test_merkle_root_deterministic()
  - test_duplicate_anchor_guard()
  - test_chain_selection_fallback()

# Lokal (Testnet):
bash scripts/autorunners/ar03_simulate.sh --testnet --dry-run
```

---

## AR-04: dora_incident_plan_gate

**SoT-Regel:** master_v1.1.1 §5 (DORA Art. 10), jeder Root MUSS `docs/incident_response_plan.md`
**Zweck:** Wöchentlicher Check ob alle 24 Roots einen DORA-Incident-Response-Plan haben

### 1. Trigger + Repo-Scope
```yaml
on:
  schedule:
    - cron: '0 6 * * 1'   # Jeden Montag 06:00 UTC
  push:
    paths: ['**/docs/incident_response_plan.md']
repos: [SSID]
```

### 2. Deterministische Checks (GitHub Action)

**Pattern:** `{ROOT}/docs/incident_response_plan.md` für alle 24 Roots

```bash
# Schritt 1: DORA-Compliance-Check (alle 24 Roots)
python 23_compliance/scripts/dora_incident_plan_check.py \
  --roots "01_ai_layer 02_audit_logging 03_core 04_deployment \
           05_documentation 06_data_pipeline 07_governance_legal 08_identity_score \
           09_meta_identity 10_interoperability 11_test_simulation 12_tooling \
           13_ui_layer 14_zero_time_auth 15_infra 16_codex \
           17_observability 18_data_layer 19_adapters 20_foundation \
           21_post_quantum_crypto 22_datasets 23_compliance 24_meta_orchestration" \
  --required-file "docs/incident_response_plan.md" \
  --template "05_documentation/templates/TEMPLATE_INCIDENT_RESPONSE.md" \
  --out /tmp/dora_check_results.json

# Schritt 2: Inhalts-Validierung (nicht nur Existenz)
python 23_compliance/scripts/dora_content_validate.py \
  --results /tmp/dora_check_results.json \
  --min-sections 5 \
  --out /tmp/dora_validation.json
```

**dora_check_results.json Format:**
```json
{
  "total_roots": 24,
  "compliant": 18,
  "missing": ["07_governance_legal", "11_test_simulation", "..."],
  "present_but_empty": ["03_core"],
  "checks": {
    "01_ai_layer": {
      "path": "01_ai_layer/docs/incident_response_plan.md",
      "exists": true,
      "size_bytes": 4512,
      "sections_found": 7
    }
  }
}
```

### 3. EMS Gate-Runner Interface
```json
{
  "autorunner_id": "AR-04",
  "scope_lock": {
    "allowed_paths": ["**/docs/incident_response_plan.md",
                      "05_documentation/templates/**"],
    "forbidden_paths": ["02_audit_logging/storage/worm/**"]
  },
  "agent_task": {
    "agent_id": "14_compliance_officer",
    "model": "sonnet",
    "max_tokens": 2048
  },
  "opa_input_path": "24_meta_orchestration/registry/generated/repo_scan.json",
  "context": {
    "dora_results_path": "/tmp/dora_check_results.json",
    "dora_validation_path": "/tmp/dora_validation.json",
    "template_path": "05_documentation/templates/TEMPLATE_INCIDENT_RESPONSE.md"
  }
}
```

**Status:** PASS | FAIL_DORA (fehlende Plans) | FAIL_POLICY (Plan leer/zu kurz)

### 4. Claude-Agent-Einsatz
**Agent:** Agent-CMP (14_compliance_officer) — **Sonnet**
**Wann:** NUR wenn Roots mit fehlendem Plan → Agent erstellt Patch mit Stub aus Template
**Scope-Lock:** Write nur auf `{missing_root}/docs/incident_response_plan.md`
**Patch-only:** Patch-Datei → EMS → PR durch PR-Integrator (Agent-07)
**Kein Direktcommit**

### 5. WORKFLOW.md Step-Mapping
1. **Plan:** scope = alle 24 Root `docs/`-Dirs; Allowlist der fehlenden
2. **Patch:** Stub `incident_response_plan.md` aus Template (wenn fehlend)
3. **Gates:** `dora_existence(policy)` → `dora_content_validate(qa)`
4. **Guard:** verhindert Doppel-Stub-Erstellung für selben Root
5. **Integrate:** PR erstellen via Agent-07 (pr-integrator)
6. **Evidence:** je Root ein Eintrag in evidence.jsonl
7. **Cleanup:** Sandbox entfernen

### 6. Concurrency
- 1 Worker (sequentiell — alle 24 Roots prüfen)
- Wenn Fixes nötig: je fehlenden Root ein isolierter Worker-Call
- Max 4 parallele Stub-Generator-Workers
- Timeout: 10 min

### 7. Tests
```
tests/autorunners/test_ar04_dora_gate.py
  - test_all_24_roots_checked()
  - test_missing_plan_triggers_patch()
  - test_template_substitution_correct()
  - test_existing_plan_not_overwritten()
  - test_empty_plan_triggers_fail_policy()

# Lokal:
bash scripts/autorunners/ar04_simulate.sh --check-only --roots "07_governance_legal 11_test_simulation"
```

---

## AR-05: shard_completion_gate

**SoT-Regel:** master §4 (Deterministic Architecture: 24×16=384 chart.yaml), ADR-0008
**Zweck:** Stellt sicher dass die 384-Feld-Matrix vollständig und konsistent bleibt

### 1. Trigger + Repo-Scope
```yaml
on:
  push:
    paths: ['**/shards/**', '**/chart.yaml']
  pull_request:
    branches: [main]
repos: [SSID]
```

### 2. Deterministische Checks (GitHub Action)
```bash
# Schritt 1: 384-Matrix-Check
python 24_meta_orchestration/scripts/shard_completion_check.py \
  --roots 24 \
  --shards 16 \
  --expected-total 384 \
  --chart-filename chart.yaml \
  --out /tmp/shard_completion.json

# Schritt 2: Naming-Convention-Check
python 12_tooling/scripts/naming_convention_check.py \
  --shard-pattern "^[0-9]{2}_(identitaet_personen|dokumente_nachweise|...)" \
  --roots-pattern "^[0-9]{2}_(ai_layer|audit_logging|...)" \
  --out /tmp/naming_check.json

# Schritt 3: chart.yaml Schema-Validierung (für geänderte charts)
for chart in $(git diff --name-only HEAD~1 | grep chart.yaml); do
  python 16_codex/src/schema_validator.py \
    --chart "$chart" \
    --schema 16_codex/contracts/schemas/chart.schema.json
done
```

**shard_completion.json Format:**
```json
{
  "total_expected": 384,
  "total_found": 312,
  "completion_percent": 81.25,
  "missing": [
    "01_ai_layer/shards/05_gesundheit_medizin/chart.yaml",
    "..."
  ],
  "by_root": {
    "01_ai_layer": { "expected": 16, "found": 14, "missing_shards": [5,6] }
  }
}
```

### 3. EMS Gate-Runner Interface
```json
{
  "autorunner_id": "AR-05",
  "scope_lock": {
    "allowed_paths": ["**/shards/**/chart.yaml","16_codex/contracts/schemas/**"],
    "forbidden_paths": ["02_audit_logging/**","23_compliance/evidence/**"]
  },
  "agent_task": {
    "agent_id": "04_gate_runner_auditor",
    "model": "sonnet"
  },
  "opa_input_path": "24_meta_orchestration/registry/generated/repo_scan.json",
  "context": {
    "shard_completion_path": "/tmp/shard_completion.json",
    "naming_check_path": "/tmp/naming_check.json",
    "fail_on_regression": true,
    "warn_on_completion_below": 90
  }
}
```

**Status:** PASS | FAIL_SOT (Regression: weniger charts als vorher) | FAIL_POLICY (Naming)

**Wichtig:** FAIL_SOT nur bei Regression (Anzahl sinkt). Neu-fehlende Charts in neuen Roots → WARN (nicht FAIL), da iterativer Aufbau.

### 4. Claude-Agent-Einsatz
**Kein Agent in Standard-Path** — deterministischer Check.
**Agent-DBG (21_debugger) — Sonnet:** NUR bei unerwartetem Parsing-Fehler in chart.yaml
**Scope-Lock:** Read-only auf defekte chart.yaml

### 5. WORKFLOW.md Step-Mapping
1. **Plan:** scope = alle `**/shards/**/chart.yaml`
2. **Patch:** keiner (Gate-only, kein Auto-Erstellen von chart.yaml)
3. **Gates:** `matrix_count(sot)` → `naming_convention(policy)` → `schema_validate(qa)`
4. **Guard:** keine Regression-Duplikate
5. **Integrate:** N/A
6. **Evidence:** Completion-Prozentsatz + fehlende Paths in evidence.jsonl
7. **Cleanup:** `/tmp/shard_*` löschen

### 6. Concurrency
- 1 Worker (zählt alle 384 Felder)
- Timeout: 5 min

### 7. Tests
```
tests/autorunners/test_ar05_shard_gate.py
  - test_full_384_matrix_passes()
  - test_regression_one_less_fails()
  - test_new_missing_chart_warns_not_fails()
  - test_naming_convention_enforced()
  - test_chart_schema_validated()
```

---

## AR-06: doc_generation

**SoT-Regel:** master §10 (Documentation as Code), chart.yaml → Markdown
**Zweck:** Bei Merge auf main: chart.yaml-Änderungen auto-generieren zu Markdown in `05_documentation/`

### 1. Trigger + Repo-Scope
```yaml
on:
  push:
    branches: [main]
    paths: ['**/chart.yaml','**/manifest.yaml','**/contracts/**/*.openapi.yaml']
repos: [SSID]
```

### 2. Deterministische Checks (GitHub Action)
```bash
# Schritt 1: Geänderte chart.yaml finden
git diff --name-only HEAD~1 | grep chart.yaml > /tmp/changed_charts.txt

# Schritt 2: Jinja2-Template-Render (deterministisch)
python 05_documentation/scripts/generate_from_chart.py \
  --charts /tmp/changed_charts.txt \
  --template 05_documentation/templates/chart_to_markdown.j2 \
  --out-dir 05_documentation/generated/ \
  --out-manifest /tmp/doc_gen_manifest.json

# Schritt 3: OpenAPI → Swagger-Artifacts
for spec in $(git diff --name-only HEAD~1 | grep openapi.yaml); do
  python 05_documentation/scripts/openapi_to_docs.py \
    --spec "$spec" \
    --out-dir "05_documentation/api/$(dirname $spec)/"
done
```

### 3. EMS Gate-Runner Interface
```json
{
  "autorunner_id": "AR-06",
  "scope_lock": {
    "allowed_paths": ["05_documentation/generated/**",
                      "05_documentation/api/**"],
    "forbidden_paths": ["**/chart.yaml","**/manifest.yaml",
                        "02_audit_logging/**","23_compliance/**"]
  },
  "agent_task": {
    "agent_id": "20_documentation_curator",
    "model": "haiku",
    "max_tokens": 4096
  },
  "context": {
    "changed_charts": "/tmp/changed_charts.txt",
    "doc_gen_manifest": "/tmp/doc_gen_manifest.json",
    "target_dir": "05_documentation/generated/"
  }
}
```

**Status:** PASS | FAIL_POLICY (Template-Render-Fehler) | FAIL_QA (generierte Docs leer)

### 4. Claude-Agent-Einsatz
**Agent:** Agent-DOC (20_documentation_curator) — **Haiku**
**Wann:** NUR wenn Jinja2-Template nicht ausreicht (z.B. komplexe Capability-Beschreibungen)
**Scope-Lock:** Write nur auf `05_documentation/generated/` und `05_documentation/api/`
**Patch-only → PR durch Agent-07**

### 5. WORKFLOW.md Step-Mapping
1. **Plan:** scope = geänderte charts + Ziel-Docs-Dirs
2. **Patch:** generierte `.md`-Dateien in `05_documentation/generated/`
3. **Gates:** `template_render(qa)` → `doc_not_empty(policy)`
4. **Guard:** verhindert Doppel-Generierung für selben chart-Commit
5. **Integrate:** PR erstellen mit generierten Docs
6. **Evidence:** je generiertem Doc ein Eintrag (source-chart-sha256 → doc-sha256)
7. **Cleanup:** `/tmp/changed_charts.txt` etc.

### 6. Concurrency
- 1 Worker pro geändertem Root (max 24 parallel — unwahrscheinlich)
- Timeout: 10 min

### 7. Tests
```
tests/autorunners/test_ar06_doc_generation.py
  - test_chart_yaml_renders_to_markdown()
  - test_openapi_generates_swagger_artifacts()
  - test_empty_doc_fails_qa()
  - test_idempotent_generation()   # Zweimal laufen = selbes Ergebnis
```

---

## AR-07: forbidden_extensions

**SoT-Regel:** master_v1.1.1 §6 — zusätzlich blockierte Extensions: `.ipynb .parquet .sqlite .db`
**Zweck:** Verhindert Notebook/Daten-Artefakte und lokale DBs im Repo

### 1. Trigger + Repo-Scope
```yaml
on:
  push:
    branches: ['**']
  pull_request:
    branches: [main, develop]
repos: [SSID, SSID-EMS, SSID-docs, SSID-open-core, SSID-orchestrator]
```

### 2. Deterministische Checks (GitHub Action)

**Vollständig deterministisch — KEIN Agent.**

```bash
# Schritt 1: Forbidden Extensions in geänderten Dateien
FORBIDDEN_EXTS=".ipynb .parquet .sqlite .db .env .pem .key .p12 .pfx"

python 12_tooling/scripts/forbidden_ext_check.py \
  --extensions "$FORBIDDEN_EXTS" \
  --changed-files "$(git diff --name-only HEAD~1)" \
  --also-scan-staged true \
  --out /tmp/forbidden_ext_results.json

# Schritt 2: Auch vollständiger Repo-Scan (für neue Branches)
if [ "$GITHUB_EVENT_NAME" = "pull_request" ]; then
  python 12_tooling/scripts/forbidden_ext_check.py \
    --extensions "$FORBIDDEN_EXTS" \
    --scan-all true \
    --exclude ".git/** node_modules/** .venv/**" \
    --out /tmp/forbidden_ext_full.json
fi

# Schritt 3: repo_scan.json erzeugen (für EMS)
python 24_meta_orchestration/scripts/generate_repo_scan.py \
  --repo-root . --commit-sha "$GITHUB_SHA" \
  --out 24_meta_orchestration/registry/generated/repo_scan.json
```

**forbidden_ext_results.json Format:**
```json
{
  "violations": [
    { "file": "06_data_pipeline/analysis.ipynb", "ext": ".ipynb",
      "sha256": "hex", "sot_rule": "master_v1.1.1_§6" }
  ],
  "total_checked": 42,
  "total_violations": 1
}
```

### 3. EMS Gate-Runner Interface
```json
{
  "autorunner_id": "AR-07",
  "scope_lock": {
    "allowed_paths": ["**"],
    "forbidden_paths": [".git/**","node_modules/**",".venv/**"]
  },
  "agent_task": null,
  "opa_input_path": "24_meta_orchestration/registry/generated/repo_scan.json",
  "context": {
    "forbidden_ext_results": "/tmp/forbidden_ext_results.json",
    "forbidden_extensions": [".ipynb",".parquet",".sqlite",".db",
                              ".env",".pem",".key",".p12",".pfx"]
  }
}
```

**Status:** PASS | FAIL_FORBIDDEN (Extension gefunden)
**Exit-Code:** 1 (Action schlägt fehl, PR wird blockiert)

### 4. Claude-Agent-Einsatz
**KEIN AGENT.** Vollständig deterministisch.
Rationale: Extension-Check ist binär — keine AI-Bewertung nötig.

### 5. WORKFLOW.md Step-Mapping
1. **Plan:** scope = alle geänderten/neuen Dateien
2. **Patch:** keiner
3. **Gates:** `forbidden_ext(policy)` → OPA-Validation
4. **Guard:** N/A (first-check-wins)
5. **Integrate:** N/A — Gate-only
6. **Evidence:** Violations-Liste in evidence.jsonl
7. **Cleanup:** `/tmp/forbidden_ext_*` löschen

### 6. Concurrency
- 1 Worker (schnell, < 10s)
- Timeout: 3 min
- Alle 5 Repos parallel auslösbar

### 7. Tests
```
tests/autorunners/test_ar07_forbidden_extensions.py
  - test_clean_repo_passes()
  - test_ipynb_in_push_fails()
  - test_sqlite_in_pr_fails()
  - test_parquet_in_data_pipeline_fails()
  - test_gitignored_file_excluded()        # .venv/.ipynb nicht gepusht → ok
  - test_all_5_repos_covered()

# Lokal (schnellster Test):
python 12_tooling/scripts/forbidden_ext_check.py --scan-all true --dry-run
```

---

## AR-08: opencore_sync

**SoT-Regel:** opencore_export_policy.yaml (deny_globs + secret_scan_regex)
**Zweck:** Bei Merge auf main in SSID: sichere, gefilterte Sync nach SSID-open-core

### 1. Trigger + Repo-Scope
```yaml
on:
  push:
    branches: [main]
repos: [SSID → SSID-open-core]
```

### 2. Deterministische Checks (GitHub Action)
```bash
# Schritt 1: Secret-Scan BEVOR irgendwas übertragen wird
python 12_tooling/scripts/secret_scanner.py \
  --patterns "$(cat 16_codex/opencore_export_policy.yaml | yq .secret_scan_regex[])" \
  --changed-files "$(git diff --name-only HEAD~1)" \
  --out /tmp/secret_scan_results.json

# Erwartete Patterns (aus opencore_export_policy.yaml):
# - "BEGIN (RSA|OPENSSH|EC) PRIVATE KEY"
# - "AKIA[0-9A-Z]{16}"                 (AWS Access Key)
# - "xox[baprs]-"                       (Slack Token)
# - "ghp_[A-Za-z0-9]{36}"             (GitHub PAT)
# - "-----BEGIN PRIVATE KEY-----"

# Schritt 2: deny_globs-Filter anwenden
python 12_tooling/scripts/apply_deny_globs.py \
  --policy 16_codex/opencore_export_policy.yaml \
  --source-dir . \
  --out /tmp/files_to_sync.json

# deny_globs (aus opencore_export_policy.yaml):
# - "02_audit_logging/storage/worm/**"
# - "02_audit_logging/evidence/**"
# - "24_meta_orchestration/registry/logs/**"
# - "security/results/**"

# Schritt 3: Diff zwischen SSID-main und SSID-open-core berechnen
python 12_tooling/scripts/opencore_diff.py \
  --source . \
  --target-repo "SSID-open-core" \
  --allowed-files /tmp/files_to_sync.json \
  --out /tmp/opencore_diff.json
```

### 3. EMS Gate-Runner Interface
```json
{
  "autorunner_id": "AR-08",
  "scope_lock": {
    "allowed_paths": ["(alle Pfade AUSSER deny_globs)"],
    "forbidden_paths": [
      "02_audit_logging/storage/worm/**",
      "02_audit_logging/evidence/**",
      "24_meta_orchestration/registry/logs/**",
      "security/results/**"
    ]
  },
  "agent_task": {
    "agent_id": "08_ops_runner",
    "model": "sonnet"
  },
  "context": {
    "secret_scan_results": "/tmp/secret_scan_results.json",
    "files_to_sync": "/tmp/files_to_sync.json",
    "opencore_diff": "/tmp/opencore_diff.json",
    "target_repo": "EduBrainBoost/SSID-open-core"
  }
}
```

**Status:** PASS | FAIL_FORBIDDEN (Secret gefunden) | FAIL_POLICY (deny_glob verletzt) | ERROR

### 4. Claude-Agent-Einsatz
**Agent:** Agent-OPS (08_ops_runner) — **Sonnet**
**Agent-SEC (05_security_compliance) — Opus:** NUR wenn Secret-Scanner Borderline-Match hat
**Wann:** Für die eigentliche Sync-Operation (git push / PR zum open-core Repo)
**Scope-Lock:** Write nur auf `SSID-open-core/` (nicht SSID selbst)
**Patch-only:** Sync-Patch → PR in SSID-open-core durch Agent-07

### 5. WORKFLOW.md Step-Mapping
1. **Plan:** scope = erlaubte Dateien (nach deny_globs)
2. **Patch:** Diff → SSID-open-core als Sync-Branch
3. **Gates:** `secret_scan(policy)` → `deny_globs(policy)` → `diff_validate(qa)`
4. **Guard:** verhindert Doppel-Sync für selben Commit
5. **Integrate:** PR in SSID-open-core; Auto-Merge wenn Tests grün
6. **Evidence:** Sync-Manifest (welche Dateien übertragen, welche gefiltert)
7. **Cleanup:** Sync-Branch wenn merged

### 6. Concurrency
- 1 Worker (Sync ist sequentiell)
- Timeout: 15 min

### 7. Tests
```
tests/autorunners/test_ar08_opencore_sync.py
  - test_worm_storage_excluded()
  - test_evidence_excluded()
  - test_secret_in_code_blocks_sync()   # Secret-Scanner schlägt an
  - test_clean_code_syncs_correctly()
  - test_deny_glob_patterns_correct()

# Lokal:
bash scripts/autorunners/ar08_simulate.sh --dry-run --target /tmp/opencore_test/
```

---

## AR-09: bias_fairness_audit

**SoT-Regel:** master §8 (Bias-Aware AI/ML), master_v1.1.1 (Quarterly Bias Audits)
**Zweck:** Quartalsweiser Bias/Fairness-Audit aller AI/ML-Modelle in Root 01

### 1. Trigger + Repo-Scope
```yaml
on:
  schedule:
    - cron: '0 4 1 */3 *'   # Quartalsweise (1. jedes 3. Monats, 04:00)
  workflow_dispatch:
repos: [SSID]
paths: ['01_ai_layer/**','08_identity_score/**','22_datasets/**']
```

### 2. Deterministische Checks (GitHub Action)
```bash
# Schritt 1: Modell-Inventar aufbauen
python 01_ai_layer/scripts/model_inventory.py \
  --scan-dirs "01_ai_layer 08_identity_score" \
  --out /tmp/model_inventory.json

# Schritt 2: Fairness-Metriken (deterministisch: Demographic Parity, Equal Opportunity)
python 01_ai_layer/scripts/fairness_metric_calc.py \
  --models /tmp/model_inventory.json \
  --metrics "demographic_parity equal_opportunity" \
  --test-dataset 22_datasets/bias_test_suite.yaml \
  --out /tmp/fairness_metrics.json

# Schritt 3: Fair-Growth-Rule Check (POFI-Scoring)
python 08_identity_score/scripts/pofi_audit.py \
  --policy 07_governance_legal/proof_of_fairness_policy.yaml \
  --out /tmp/pofi_audit.json
```

### 3. EMS Gate-Runner Interface
```json
{
  "autorunner_id": "AR-09",
  "scope_lock": {
    "allowed_paths": ["01_ai_layer/**","08_identity_score/**",
                      "22_datasets/**","07_governance_legal/**"],
    "forbidden_paths": ["02_audit_logging/storage/worm/**","**/pii/**"]
  },
  "agent_task": {
    "agent_id": "29_autoresearcher",
    "model": "opus",
    "max_tokens": 8192
  },
  "opa_input_path": "24_meta_orchestration/registry/generated/repo_scan.json",
  "context": {
    "model_inventory": "/tmp/model_inventory.json",
    "fairness_metrics": "/tmp/fairness_metrics.json",
    "pofi_audit": "/tmp/pofi_audit.json",
    "thresholds": {
      "demographic_parity_max_diff": 0.05,
      "equal_opportunity_min": 0.95
    }
  }
}
```

**Status:** PASS | FAIL_POLICY (Bias-Threshold überschritten) | FAIL_QA (Modell nicht testbar)

### 4. Claude-Agent-Einsatz
**Agent:** Agent-ARS (29_autoresearcher) — **Opus**
**Wann:** Für tiefe Analyse der Fairness-Metriken und Empfehlungen zur Bias-Mitigation
**Agent-CMP (14_compliance_officer) — Sonnet:** für Compliance-Report-Erstellung
**Scope-Lock:** Read-only auf Modell-Artefakte; Write auf `01_ai_layer/docs/bias_audit_reports/`
**Output:** Quarterly Bias Report (MD) → evidence.jsonl + `02_audit_logging/reports/bias_audit_Q<N>_<YEAR>.md`

### 5. WORKFLOW.md Step-Mapping
1. **Plan:** scope = Modell-Inventar + Fairness-Test-Suite
2. **Patch:** Bias-Audit-Report in `01_ai_layer/docs/bias_audit_reports/`
3. **Gates:** `fairness_threshold(policy)` → `pofi_check(sot)` → `report_not_empty(qa)`
4. **Guard:** verhindert Doppel-Audit im selben Quartal
5. **Integrate:** PR mit Audit-Report
6. **Evidence:** Fairness-Metriken + Quartal in evidence.jsonl
7. **Cleanup:** Modell-Scan-Artefakte

### 6. Concurrency
- 1 Worker für Inventar; dann je Modell-Typ 1 Worker
- Max 3 parallel
- Timeout: 45 min (Modelle brauchen Zeit)

### 7. Tests
```
tests/autorunners/test_ar09_bias_audit.py
  - test_model_inventory_complete()
  - test_demographic_parity_threshold_enforced()
  - test_quarterly_guard_prevents_double_run()
  - test_report_generated_in_correct_path()
  - test_pofi_formula_correct()   # POFI = log(activity+1)/log(rewards+10)
```

---

## AR-10: fee_distribution_audit

**SoT-Regel:** gebuehren_abo_modelle v5.4.3 (7-Säulen + Quarterly Merkle-Proof Reporting)
**Zweck:** Quartalsweiser Audit der Fee-Distribution-Implementierung gegen SoT-Policy

### 1. Trigger + Repo-Scope
```yaml
on:
  schedule:
    - cron: '0 0 1 */3 *'   # Gleich wie cron_quarterly_audit (koordiniert)
  workflow_dispatch:
repos: [SSID]
paths: ['03_core/fee_distribution_engine.py',
        '03_core/subscription_revenue_distributor.py',
        '07_governance_legal/**',
        '23_compliance/fee_allocation_policy.yaml']
```

### 2. Deterministische Checks (GitHub Action)
```bash
# Schritt 1: 7-Säulen-Policy gegen Implementierung prüfen
python 23_compliance/scripts/fee_policy_audit.py \
  --policy 23_compliance/fee_allocation_policy.yaml \
  --implementation 03_core/fee_distribution_engine.py \
  --sot-doc "16_codex/SSID_structure_gebuehren_abo_modelle.md" \
  --out /tmp/fee_policy_check.json

# Erwartete Verteilung (aus SoT):
# Legal/Compliance: 0.35%, Audit/Security: 0.30%, Tech Maintenance: 0.30%
# DAO Treasury: 0.25%, Community Bonus: 0.20%, Liquidity Reserve: 0.20%
# Marketing: 0.20% → Summe = 2.00% genau

# Schritt 2: Subscription-Revenue-Distributor (50/30/10/10)
python 23_compliance/scripts/subscription_audit.py \
  --policy 07_governance_legal/subscription_revenue_policy.yaml \
  --implementation 03_core/subscription_revenue_distributor.py \
  --out /tmp/subscription_audit.json

# Schritt 3: POFI-Formel-Validierung
python 23_compliance/scripts/pofi_formula_check.py \
  --policy 07_governance_legal/proof_of_fairness_policy.yaml \
  --out /tmp/pofi_formula_check.json

# Schritt 4: DAO-Parameter-Ranges prüfen
python 23_compliance/scripts/dao_params_check.py \
  --policy 07_governance_legal/subscription_revenue_policy.yaml \
  --out /tmp/dao_params.json
```

### 3. EMS Gate-Runner Interface
```json
{
  "autorunner_id": "AR-10",
  "scope_lock": {
    "allowed_paths": ["03_core/**","07_governance_legal/**",
                      "23_compliance/**","08_identity_score/**"],
    "forbidden_paths": ["02_audit_logging/storage/worm/**","**/secrets/**"]
  },
  "agent_task": {
    "agent_id": "14_compliance_officer",
    "model": "sonnet",
    "max_tokens": 4096
  },
  "opa_input_path": "24_meta_orchestration/registry/generated/repo_scan.json",
  "context": {
    "fee_policy_check": "/tmp/fee_policy_check.json",
    "subscription_audit": "/tmp/subscription_audit.json",
    "pofi_formula_check": "/tmp/pofi_formula_check.json",
    "dao_params": "/tmp/dao_params.json",
    "expected_7_saeulen_sum": "2.00"
  }
}
```

**Status:** PASS | FAIL_POLICY (Verteilung stimmt nicht mit SoT) | FAIL_QA (Formel-Fehler)

### 4. Claude-Agent-Einsatz
**Agent:** Agent-CMP (14_compliance_officer) — **Sonnet**
**Agent-CRY (13_crypto_auditor) — Opus:** für Merkle-Proof-Validierung und Smart-Contract-Review
**Wann:** Wenn Policy vs. Implementierung abweicht: tiefe Analyse + Gap-Report
**Scope-Lock:** Read-only auf alle Audit-Targets
**Output:** Quarterly Fee-Distribution-Report → `02_audit_logging/reports/fee_distribution_Q<N>_<YEAR>.md`

### 5. WORKFLOW.md Step-Mapping
1. **Plan:** scope = alle Fee-relevanten Dateien
2. **Patch:** Audit-Report-Datei in `02_audit_logging/reports/`
3. **Gates:** `fee_policy_match(policy)` → `sot_7saeulen_sum(sot)` → `merkle_proof(qa)`
4. **Guard:** verhindert Doppel-Audit gleichen Quartals
5. **Integrate:** PR mit Audit-Report
6. **Evidence:** Fee-Distribution-Snapshot in evidence.jsonl
7. **Cleanup:** `/tmp/fee_*` und `/tmp/subscription_*` löschen

### 6. Concurrency
- 1 Worker (Audit ist sequentiell)
- Timeout: 20 min

### 7. Tests
```
tests/autorunners/test_ar10_fee_audit.py
  - test_7_saeulen_sum_exactly_2_percent()
  - test_subscription_50_30_10_10_model()
  - test_pofi_formula_matches_sot()
  - test_dao_params_within_governance_ranges()
  - test_quarterly_guard_correct()
  - test_merkle_proof_fee_distribution()
```

---

## Gesamt-Übersicht: 10 AutoRunner

| # | Name | Trigger | Repos | Agent | Model | AI-Optional? |
|---|------|---------|-------|-------|-------|-------------|
| AR-01 | pii_scanner | push/PR | SSID,EMS,OC | SEC-05 | Opus | Ja (borderline) |
| AR-02 | contract_tests | push/PR | SSID | AUD-04+API-24 | Sonnet | Ja (Fehler) |
| AR-03 | evidence_anchoring | hourly | SSID | OPS-08+OBS-17 | Haiku | Ja (Fehler) |
| AR-04 | dora_incident_plan | weekly | SSID | CMP-14 | Sonnet | Ja (Stubs) |
| AR-05 | shard_completion | push/PR | SSID | DBG-21 | Sonnet | Ja (Fehler) |
| AR-06 | doc_generation | push main | SSID | DOC-20 | Haiku | Ja (komplex) |
| AR-07 | forbidden_extensions | push/PR | alle | — | — | **Nein** |
| AR-08 | opencore_sync | push main | SSID→OC | OPS-08+SEC-05 | Sonnet | Ja (Borderline) |
| AR-09 | bias_fairness | quarterly | SSID | ARS-29+CMP-14 | Opus | **Ja (Kern)** |
| AR-10 | fee_distribution | quarterly | SSID | CMP-14+CRY-13 | Sonnet | Ja (Gaps) |

**AQ-Regeln (aus GLOBAL CLAUDE.md):**
- AQ-1: isolation="worktree" IMMER für Agent-Calls
- AQ-2: Critical=Opus, Standard=Sonnet, Lightweight=Haiku
- AQ-3: mode="auto" oder "default" — NIEMALS "bypassPermissions"
- AQ-4: Agents committen NICHT — nur Orchestrator nach Review
- AQ-5: Jeder Agent bekommt explizite File-Liste (Scope-Lock oben)
- AQ-6: Review vor Integration (Diff + Lint + Tests)

---

## Implementierungsplan (APPLY PLAN — kein GO noch)

### Neue Dateien zu erstellen

**GitHub Actions (`SSID/.github/workflows/`):**
- `pii_scanner.yml`
- `contract_tests.yml`
- `evidence_anchoring.yml`
- `dora_incident_plan_gate.yml`
- `shard_completion_gate.yml`
- `doc_generation.yml`
- `forbidden_extensions.yml`
- `opencore_sync.yml`
- `bias_fairness_audit.yml`
- `fee_distribution_audit.yml`

**Scripts (`SSID/12_tooling/scripts/`):**
- `forbidden_ext_check.py`
- `secret_scanner.py`
- `apply_deny_globs.py`
- `opencore_diff.py`
- `naming_convention_check.py`
- `find_contracts.py`

**Scripts (`SSID/24_meta_orchestration/scripts/`):**
- `generate_repo_scan.py` (OPA-Input Generator)
- `shard_completion_check.py`
- `sot_contract_check.py`

**Scripts (`SSID/23_compliance/scripts/`):**
- `pii_regex_scan.py`
- `dora_incident_plan_check.py`
- `dora_content_validate.py`
- `fee_policy_audit.py`
- `subscription_audit.py`
- `pofi_formula_check.py`
- `dao_params_check.py`

**Config/Templates:**
- `23_compliance/rules/pii_patterns.yaml`
- `23_compliance/rules/pii_semgrep.yaml`
- `05_documentation/templates/TEMPLATE_INCIDENT_RESPONSE.md` (falls nicht vorhanden)
- `16_codex/contracts/schemas/chart.schema.json` (falls nicht vorhanden)

**Tests (`SSID/tests/autorunners/`):**
- `test_ar01_pii_scanner.py` ... `test_ar10_fee_audit.py`

**Lokale Simulations-Scripte (`SSID/scripts/autorunners/`):**
- `ar01_simulate.sh` ... `ar08_simulate.sh`

### Keine Änderungen an
- `.github/` in anderen Repos (außer SSID-open-core für AR-08)
- Bestehenden GitHub Actions (cron_daily_*, gates.yml, etc.)
- Root-Ordner-Struktur (keine neuen Root-Dirs)
- Root-Level-Files (root_level_exceptions.yaml enforcement respektiert)

---

**Ende Design-Dokument**
**Status:** Warten auf GO für Implementierung
**Nächster Schritt:** writing-plans Skill → konkrete Implementierungs-Tasks
