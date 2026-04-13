# ADR 0009: Include Fee Docs In Structure Spec Inputs

## Status
Accepted

## Context
`phase1` in `12_tooling/scripts/deterministic_repo_setup.py` produced `24_meta_orchestration/registry/structure_spec.json` from a partial SoT input set.
Two fee-related source documents were present in the repository but not included in `SOT_INPUT_FILES`.

## Decision
Extend `SOT_INPUT_FILES` with:
- `16_codex/SSID_structure_gebuehren_abo_modelle.md`
- `16_codex/SSID_structure_gebuehren_abo_modelle_ROOTS_16_21_ADDENDUM.md`

Also enforce hard-fail behavior in `phase1` when any required SoT input file is missing.

## Consequences
- `structure_spec.json` now reflects a 6-file SoT input set.
- Missing required SoT inputs fail fast with exit code `24`.
- `phase1` remains deterministic and idempotent when inputs are unchanged.
