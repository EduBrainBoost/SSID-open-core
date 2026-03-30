# Phase 3 Manifest Eligibility Matrix

## Decision Rule
A shard may receive `manifest.yaml` only if all required implementation conditions are provably true.

| Klasse | Bedeutung | Manifest erlaubt |
|---|---|---|
| READY_FOR_MANIFEST | reale Implementierung + Contracts + Tests + Registry + Evidence vorhanden | JA |
| BLOCKED_NO_IMPLEMENTATION | nur Scaffold/Leerverzeichnis, kein echter Implementation Path | NEIN |
| BLOCKED_NO_CONTRACTS | keine referenzierbaren Contracts/Schemas | NEIN |
| BLOCKED_NO_TESTS | keine Tests oder keine deterministische Testableitung | NEIN |
| BLOCKED_NO_REGISTRY | keine Registry-Parität | NEIN |
| BLOCKED_POLICY_MISMATCH | Policies/Constraints nicht kompatibel | NEIN |
| BLOCKED_EVIDENCE_MISSING | Evidence/Hash/Audit-Pfad fehlt | NEIN |

## Required Fields for any generated manifest
- manifest_version
- root_id
- shard_id
- chart_reference
- implementation_id
- implementation_path
- tech_stack
- entrypoints
- dependencies
- contracts_reference
- tests_reference
- evidence_reference
- registry_reference
- runtime_requirements
- compliance_constraints
- status

## Hard Rejects
- placeholder implementation path
- missing chart reference
- contracts absent
- tests absent
- evidence absent
- registry absent
- generated from assumption instead of repo fact
