# Phase 3 Manifest Template Spec

```yaml
manifest_version: "1.0"
generated_at_utc: "<UTC ISO8601>"
root_id: "01_ai_layer"
shard_id: "01_identitaet_personen"
chart_reference: "01_ai_layer/shards/01_identitaet_personen/chart.yaml"

implementation:
  id: "python-tensorflow"
  path: "01_ai_layer/shards/01_identitaet_personen/implementations/python-tensorflow"
  tech_stack: ["python", "tensorflow"]
  entrypoints:
    - "src/main.py"
  runtime:
    os: ["linux"]
    python: ">=3.12"
  dependencies:
    files:
      - "requirements.txt"
      - "requirements-dev.txt"

contracts:
  openapi:
    - "contracts/identity_risk_scoring.openapi.yaml"
    - "contracts/biometric_matching.openapi.yaml"
  schemas:
    - "contracts/schemas/did_document.schema.json"
    - "contracts/schemas/identity_evidence.schema.json"

tests:
  unit: "tests/unit"
  integration: "tests/integration"
  conformance: "conformance"

evidence:
  audit_report: "23_compliance/evidence/phase3/..."
  hash_file: "23_compliance/evidence/phase3/..."

registry:
  entry_path: "24_meta_orchestration/registry/phase3_manifest_registry.json"

constraints:
  policies:
    - "hash_only"
    - "non_custodial"
  pii_storage: "forbidden"

status: "active"
```

## Notes
- `manifest.yaml` is implementation-specific, never shard-generic.
- A shard may have multiple manifests if multiple real implementations exist.
- Every field must point to an existing artifact path or the manifest is invalid.
