# SSID → EMS Integration Hand-off Mapping

**Schema Version**: 1.0.0
**Status**: Pre-Merge Ready (awaiting EMS PR#127 merge)

## Field Mapping: SSID → EMS UI

| SSID Field | Type | EMS UI Target |
|---|---|---|
| `schema_version` | string | Compatibility Banner/Gate |
| `generated_at` | ISO-8601 string | Report Timestamp |
| `module_health[].module_name` | string | Module Name Column |
| `module_health[].status` | healthy/degraded/offline | Module Health Widget (color badge) |
| `module_health[].version` | string | Module Version |
| `module_health[].last_checked_utc` | ISO-8601 string | Last Check Timestamp |
| `flow_statuses[].flow_id` | string | Runtime Flow Identifier |
| `flow_statuses[].flow_name` | string | Flow Name Column |
| `flow_statuses[].status` | success/denied/error/degraded | Flow Status Badge |
| `flow_statuses[].allow_or_deny` | allow/deny | Policy Status Badge (green/red) |
| `flow_statuses[].input_hash` | SHA-256 hex | Input Evidence Hash |
| `flow_statuses[].output_hash` | SHA-256 hex | Output Evidence Hash |
| `flow_statuses[].proof_hash` | SHA-256 hex or null | Audit Proof Column |
| `flow_statuses[].determinism_hash` | SHA-256 hex | Determinism Proof Badge |
| `flow_statuses[].policy_decisions` | array of objects | Policy Decision Detail Panel |
| `flow_statuses[].timestamp_utc` | ISO-8601 string | Flow Timestamp |

## EMS Status Classifications

| SSID State | EMS Display |
|---|---|
| `status=success, allow_or_deny=allow` | ✅ Healthy |
| `status=denied, allow_or_deny=deny` | 🚫 Policy Denied |
| `status=error` | ❌ Error |
| `module_health.status=degraded` | ⚠️ Module Degraded |
| `module_health.status=offline` | 🔴 Module Offline |
| `proof_hash=null` | ⚠️ Evidence Missing |

## Consumption Pattern for EMS

```python
# EMS adapter (after PR#127 merge)
import json
from pathlib import Path

def consume_ssid_report(report_path: str) -> dict:
    with open(report_path, encoding="utf-8") as f:
        return json.load(f)

# Or via direct import (if SSID is in Python path):
# from ssid_runtime_reporter import SsidRuntimeReporter
# report = SsidRuntimeReporter().generate_report().to_dict()
```

## Change Policy

Schema changes require:
1. Increment `SCHEMA_VERSION` in `ems_contract.py`
2. Update `ssid_runtime_report.schema.json`
3. Add migration note to this file
4. Run backward-compat tests
