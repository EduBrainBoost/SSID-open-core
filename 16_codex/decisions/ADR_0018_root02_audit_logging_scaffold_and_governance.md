# ADR_0018_root02_audit_logging_scaffold_and_governance

## Status
Accepted

## Context
Root 02 (`02_audit_logging`) required conformance with SoT v4.1.0 under ROOT-24-LOCK.
Three phases of work were needed:
- **B1a**: Scaffold 4 MUST directories, `module.yaml`, `README.md`,
  central interface targets, and 16 shard `chart.yaml` interface wiring.
- **B1b**: Add governance rules SOT_AGENT_009/010/011 to validator, contract, REGO, and tests.
  Add registry manifest entry at `24_meta_orchestration/registry/manifests/registry_manifest.yaml`.
- **Phase C**: Rehash all 6 canonical SoT artifacts in `sot_registry.json`,
  update audit report Check D to PASS.

Per Repo Separation Guard policy, changes under `24_meta_orchestration/` require an ADR.

## Decision
We accept the Root 02 Audit Logging scaffold, governance rule additions (SOT_AGENT_009..011),
registry manifest binding, and SoT registry rehash as a single coordinated change-set.
02_audit_logging is classified as Internal Governance with evidence_infrastructure role.

## Consequences
- Positive: Root 02 fully conforms to SoT v4.1.0; all 11 SOT_AGENT rules pass; registry bound.
- Positive: Existing operational content (WORM, redaction, sandbox) preserved intact.
- Negative: Scope spans evidence module that serves cross-cutting infrastructure role.
