# ROADMAP INTERNAL

Execution source for AI work is task-spec only under `24_meta_orchestration/plans/`.

## Execution Order
1. `24_meta_orchestration/plans/PLAN_0001_repo_controls.yaml`
2. `24_meta_orchestration/plans/PLAN_0002_queue_and_gates.yaml`
3. `24_meta_orchestration/plans/PLAN_0003_testnet_proof_mvp.yaml`

## Dispatcher Rule
- Only task-spec files are executable units for AI tasks.
- Markdown roadmap text is informational and non-executable.

## Definition of Done
- Requested task-spec passes `policy`, `sot`, and `qa`.
- Write scope stays inside `allowed_paths`.
- `do_not_touch` zones remain unchanged.
- Stop conditions are honored on first hard fail.
