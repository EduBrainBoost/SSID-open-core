"""End-to-end testnet script: deploy -> verify -> report.

Orchestrates deploy_testnet and verify_testnet in sequence.
Reads RPC_URL, CHAIN_ID, and PRIVATE_KEY from environment variables.
Writes test_report.md to the audit logging directory.

Exit code 0 on full PASS, 1 on any FAIL.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    from web3 import Web3  # noqa: F401 — validate web3 is importable
except ImportError:
    print("ERROR: web3 package is not installed. Run: pip install web3")
    sys.exit(1)

from deploy_testnet import deploy
from verify_testnet import verify

__all__ = ["run_e2e"]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT: Path = Path(__file__).resolve().parents[4]
AUDIT_DIR: Path = REPO_ROOT / "02_audit_logging" / "agent_runs" / "PH3_IMPL_SCRIPTS_002"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_env() -> tuple:
    """Read required environment variables. Exits on missing values."""
    rpc_url: str | None = os.environ.get("RPC_URL")
    chain_id_str: str | None = os.environ.get("CHAIN_ID")
    private_key: str | None = os.environ.get("PRIVATE_KEY")

    missing = []
    if not rpc_url:
        missing.append("RPC_URL")
    if not chain_id_str:
        missing.append("CHAIN_ID")
    if not private_key:
        missing.append("PRIVATE_KEY")

    if missing:
        print(f"ERROR: Missing required environment variables: {missing}")
        sys.exit(1)

    try:
        chain_id = int(chain_id_str)  # type: ignore[arg-type]
    except ValueError:
        print(f"ERROR: CHAIN_ID must be an integer, got: {chain_id_str}")
        sys.exit(1)

    return rpc_url, chain_id, private_key  # type: ignore[return-value]


def _write_test_report(
    deploy_result: dict[str, Any] | None,
    verify_result: dict[str, Any] | None,
    overall: str,
    elapsed: float,
    chain_id: int,
) -> Path:
    """Write test_report.md to the audit logging directory."""
    os.makedirs(AUDIT_DIR, exist_ok=True)
    output_path: Path = AUDIT_DIR / "test_report.md"

    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    deploy_status = "PASS" if deploy_result else "FAIL"
    verify_status = verify_result.get("result", "FAIL") if verify_result else "SKIP"
    contract_addr = deploy_result.get("contract_address", "N/A") if deploy_result else "N/A"
    deploy_tx = deploy_result.get("tx_hash", "N/A") if deploy_result else "N/A"
    verify_txs = verify_result.get("tx_hashes", []) if verify_result else []

    lines = [
        "# E2E Testnet Report",
        "",
        f"**Timestamp:** {timestamp}",
        f"**Chain ID:** {chain_id}",
        f"**Overall Result:** {overall}",
        f"**Duration:** {elapsed:.1f}s",
        "",
        "## Deploy",
        "",
        "| Field | Value |",
        "|-------|-------|",
        f"| Status | {deploy_status} |",
        f"| Contract | {contract_addr} |",
        f"| TX Hash | {deploy_tx} |",
        "",
        "## Verify",
        "",
        "| Field | Value |",
        "|-------|-------|",
        f"| Status | {verify_status} |",
        f"| TX Hashes | {', '.join(verify_txs) if verify_txs else 'N/A'} |",
        "",
        "## Notes",
        "",
        "- No secrets are included in this report.",
        "- Deployer address is redacted in deployment.json.",
        "",
    ]

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Wrote {output_path}")
    return output_path


# ---------------------------------------------------------------------------
# Core E2E function
# ---------------------------------------------------------------------------


def run_e2e(
    rpc_url: str,
    chain_id: int,
    private_key: str,
) -> str:
    """Run the full deploy+verify E2E flow.

    Args:
        rpc_url: JSON-RPC endpoint URL.
        chain_id: Target chain ID.
        private_key: Deployer/caller private key (hex string).

    Returns:
        "PASS" or "FAIL".
    """
    start = time.monotonic()
    deploy_result: dict[str, Any] | None = None
    verify_result: dict[str, Any] | None = None

    # --- Step 1: Deploy ---
    print("=" * 60)
    print("E2E Step 1: Deploy ProofRegistry")
    print("=" * 60)

    try:
        deploy_result = deploy(rpc_url, chain_id, private_key)
    except Exception as exc:
        print(f"ERROR: Deploy failed: {exc}")
        elapsed = time.monotonic() - start
        _write_test_report(None, None, "FAIL", elapsed, chain_id)
        return "FAIL"

    contract_address: str = deploy_result["contract_address"]
    print(f"Deployed to {contract_address}")

    # Write deployment.json (same as deploy_testnet standalone).
    os.makedirs(AUDIT_DIR, exist_ok=True)
    deployment_path = AUDIT_DIR / "deployment.json"
    with open(deployment_path, "w", encoding="utf-8") as f:
        json.dump(deploy_result, f, indent=2, sort_keys=True)

    # --- Step 2: Verify ---
    print()
    print("=" * 60)
    print("E2E Step 2: Verify ProofRegistry")
    print("=" * 60)

    try:
        verify_result = verify(contract_address, rpc_url, chain_id, private_key)
    except Exception as exc:
        print(f"ERROR: Verify failed: {exc}")
        elapsed = time.monotonic() - start
        _write_test_report(deploy_result, None, "FAIL", elapsed, chain_id)
        return "FAIL"

    # Write verify_report.json (same as verify_testnet standalone).
    verify_path = AUDIT_DIR / "verify_report.json"
    with open(verify_path, "w", encoding="utf-8") as f:
        json.dump(verify_result, f, indent=2, sort_keys=True)

    # --- Overall result ---
    elapsed = time.monotonic() - start
    overall = verify_result.get("result", "FAIL")
    _write_test_report(deploy_result, verify_result, overall, elapsed, chain_id)

    print()
    print("=" * 60)
    print(f"E2E Result: {overall} ({elapsed:.1f}s)")
    print("=" * 60)

    return overall


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Entry point for e2e_testnet."""
    rpc_url, chain_id, private_key = _read_env()

    result = run_e2e(rpc_url, chain_id, private_key)

    if result == "PASS":
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
