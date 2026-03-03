# ADR_0017_root01_ai_layer_scaffold_and_governance

## Status
Accepted

## Context
Root 01 (`01_ai_layer`) required conformance with SoT v4.1.0 under ROOT-24-LOCK.
Three phases of work were needed:
- **B1a**: Scaffold 13 MUST directories, `module.yaml`, `README.md`, `model_registry.yaml`,
  central interface targets, and 16 shard `chart.yaml` interface wiring.
- **B1b**: Add governance rules SOT_AGENT_006/007/008 to validator, contract, REGO, and tests.
  Create registry manifest binding at `24_meta_orchestration/registry/manifests/registry_manifest.yaml`.
- **Phase C**: Implement SOT_AGENT_005 (`check_no_duplicate_rules()`), rehash all 6 canonical
  SoT artifacts in `sot_registry.json`, update audit report Check D to PASS.

Per Repo Separation Guard policy, changes under `24_meta_orchestration/` require an ADR.

## Decision
We accept the Root 01 AI Layer scaffold, governance rule additions (SOT_AGENT_005..008),
registry manifest binding, and SoT registry rehash as a single coordinated change-set.
All changes are advisory-only and introduce no autonomous write access.

## Consequences
- Positive: Root 01 fully conforms to SoT v4.1.0; all 8 SOT_AGENT rules pass; registry bound.
- Positive: SOT_AGENT_005 closes the contract-validator consistency gap (was dead code).
- Negative: 45-file change-set is large but atomic (B1a/B1b/C are sequentially dependent).
