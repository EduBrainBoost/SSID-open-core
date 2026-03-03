# Testnet MVP Runbook

## Required Environment Variables

| Variable | Description | Required For |
|----------|-------------|-------------|
| `RPC_URL` | JSON-RPC endpoint (e.g. Sepolia, Goerli) | deploy, verify, e2e |
| `CHAIN_ID` | Target chain ID (e.g. 11155111 for Sepolia) | deploy |
| `PRIVATE_KEY` | Deployer wallet private key (hex, no 0x prefix) | deploy, verify |
| `CONTRACT_ADDRESS` | Deployed ProofRegistry address | verify, e2e |

## Security Policy

- **Testnet keys**: May be stored in GitHub Environment `testnet` for CI
- **Prod keys**: Local-only. NEVER in CI, NEVER committed, NEVER in env files
- **No secrets in repo**: No `.env` files, no hardcoded keys, no example keys

## 1-Command Flow

### Deploy
```bash
python 12_tooling/testnet_mvp/01_hash_only_proof_registry/scripts/deploy_testnet.py
```
Writes `deployment.json` (redacted) to agent_runs.

### Verify
```bash
python 12_tooling/testnet_mvp/01_hash_only_proof_registry/scripts/verify_testnet.py
```
Round-trip: hasProof(false) → addProof → hasProof(true). Writes `verify_report.json`.

### E2E (deploy + verify)
```bash
python 12_tooling/testnet_mvp/01_hash_only_proof_registry/scripts/e2e_testnet.py
```
Orchestrates full deploy→verify flow. Writes `test_report.md`.

### Pytest (skip without ENV)
```bash
pytest -m testnet -v
```
Skips gracefully when ENV vars are absent. No failures in CI.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `RPC_URL not set` | Export RPC_URL with your testnet endpoint |
| `PRIVATE_KEY not set` | Export hex private key (no 0x prefix) |
| `Transaction reverted` | Check wallet has testnet ETH (faucet) |
| `Connection timeout` | Verify RPC endpoint is reachable |
| `proof already exists` | Contract rejects duplicate hashes |

## References
- Deploy script: `PH3_DEPLOY_SCRIPT_001`
- Verify script: `PH3_VERIFY_SCRIPT_001`
- E2E tests: `PH3_E2E_PYTEST_001`
