# Runtime Smoke Check

Deterministic reachability check for SSID runtime services.
Stdlib-only (no external dependencies).

## Usage

```bash
python 12_tooling/cli/runtime_smoke.py \
  --config 12_tooling/ops/runtime_smoke/targets.local.json \
  --write-evidence
```

Exit code: `0` = PASS (all targets PASS or SKIP), `1` = FAIL.

## Config Format (`targets.local.json`)

```json
{
  "schema_version": "1.0",
  "timeout_sec": 3,
  "targets": [
    { "name": "service_name", "kind": "http", "url": "http://localhost:PORT/path", "allow_status": [200] },
    { "name": "ws_service",   "kind": "ws",   "url": "ws://localhost:PORT/ws",     "mode": "skip" }
  ]
}
```

### Target Fields

| Field | Required | Description |
|---|---|---|
| `name` | yes | Unique identifier for the target |
| `kind` | yes | `http` or `ws` |
| `url` | yes | Full URL to check |
| `allow_status` | no | List of HTTP status codes considered PASS (default: 200-399) |
| `mode` | no | `skip` for WS targets — produces SKIP instead of FAIL |
| `timeout_sec` | no | Per-target timeout override |

### `allow_status`

By default, HTTP status codes 200-399 are considered PASS. To accept additional codes
(e.g., 401 for an auth-gated endpoint that proves reachability), add them to `allow_status`:

```json
{ "name": "orchestrator_api", "kind": "http", "url": "http://localhost:3210/api/", "allow_status": [200, 401] }
```

### WebSocket `mode: skip`

Python stdlib has no WebSocket client. WS targets with `mode: "skip"` produce
`status: "SKIP"` with a `skip_reason` and do not cause the overall run to FAIL.

## Evidence Output

When `--write-evidence` is set, a JSON file is written to:

```
23_compliance/evidence/ci_runs/runtime_smoke_results/RUNTIME_SMOKE_<sha256>.json
```

The filename contains the SHA-256 of the JSON payload, ensuring deterministic and
content-addressable evidence files. Use `--evidence-dir` to override the base directory.

## Tests

```bash
python -m pytest -q 11_test_simulation/tests_ops/test_runtime_smoke_lib.py
```
