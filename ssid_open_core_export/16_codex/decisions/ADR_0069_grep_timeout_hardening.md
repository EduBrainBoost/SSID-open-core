# ADR_0069: Grep Timeout Hardening (TS030)

## Status
Accepted

## Context
Local pytest runs timed out on `grep -r` scanning large untracked evidence directories
(05_documentation, agent_runs). Additionally, `compiler_manifest.json` hashes drifted
from actual ABI/bytecode files in both SoT and deploy locations.

## Decision
- Replace all `grep -r` / `rglob` claims scanners with `git ls-files` (tracked-only).
- Add 2MB size cap and binary skip to all scan paths.
- Align `compiler_manifest.json` hashes in both `24_meta_orchestration/contracts/`
  and `12_tooling/testnet_mvp/01_hash_only_proof_registry/contracts/`.
- Update `sot_registry.json` hash for `run_all_gates.py`.

## Consequences
- Positive: Eliminates 10 local pytest failures (timeouts + false positives + hash drift).
- Positive: Deterministic scan scope (tracked files only, sorted, size-capped).
- Negative: None identified. CI behavior unchanged.
