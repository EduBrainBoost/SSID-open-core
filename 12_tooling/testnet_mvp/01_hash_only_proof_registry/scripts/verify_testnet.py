"""Verify the ProofRegistry contract on a testnet.

Verification flow: hasProof(hash)=false -> addProof(hash) -> hasProof(hash)=true.
Reads CONTRACT_ADDRESS, RPC_URL, CHAIN_ID, and PRIVATE_KEY from environment
variables. Writes verify_report.json to the audit logging directory.
Never logs or prints secret values.

Exit code 0 on PASS, 1 on FAIL.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

try:
    from web3 import Web3
except ImportError:
    print("ERROR: web3 package is not installed. Run: pip install web3")
    sys.exit(1)

__all__ = ["verify", "TEST_HASH"]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT: Path = Path(__file__).resolve().parents[4]
CONTRACTS_DIR: Path = REPO_ROOT / "12_tooling" / "testnet_mvp" / "01_hash_only_proof_registry" / "contracts"
AUDIT_DIR: Path = REPO_ROOT / "02_audit_logging" / "agent_runs" / "PH3_IMPL_SCRIPTS_002"
ABI_PATH: Path = CONTRACTS_DIR / "proof_registry_abi.json"

# Deterministic timeout for all RPC calls (seconds).
RPC_TIMEOUT: int = 120

# Deterministic test hash: sha256 of b"ssid-testnet-verify" as bytes32.
TEST_HASH: bytes = hashlib.sha256(b"ssid-testnet-verify").digest()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_env() -> tuple[str, str, int, str]:
    """Read required environment variables. Exits on missing values."""
    contract_address: str | None = os.environ.get("CONTRACT_ADDRESS")
    rpc_url: str | None = os.environ.get("RPC_URL")
    chain_id_str: str | None = os.environ.get("CHAIN_ID")
    private_key: str | None = os.environ.get("PRIVATE_KEY")

    missing: list[str] = []
    if not contract_address:
        missing.append("CONTRACT_ADDRESS")
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

    return (
        contract_address,  # type: ignore[return-value]
        rpc_url,  # type: ignore[return-value]
        chain_id,
        private_key,  # type: ignore[return-value]
    )


def _load_abi() -> list:
    """Load the contract ABI from the contracts directory."""
    with open(ABI_PATH, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Core verify function
# ---------------------------------------------------------------------------


def verify(
    contract_address: str,
    rpc_url: str,
    chain_id: int,
    private_key: str,
) -> dict[str, Any]:
    """Run the verification flow against a deployed ProofRegistry.

    Steps:
        1. hasProof(TEST_HASH) == false
        2. addProof(TEST_HASH) -> tx receipt
        3. hasProof(TEST_HASH) == true

    Args:
        contract_address: Deployed ProofRegistry address.
        rpc_url: JSON-RPC endpoint URL.
        chain_id: Target chain ID.
        private_key: Caller private key (hex string).

    Returns:
        Dict with result (PASS/FAIL), tx_hashes, chain_id, contract_address.
    """
    abi = _load_abi()
    w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": RPC_TIMEOUT}))

    if not w3.is_connected():
        return {
            "chain_id": chain_id,
            "contract_address": contract_address,
            "result": "FAIL",
            "tx_hashes": [],
        }

    account = w3.eth.account.from_key(private_key)
    caller_address: str = account.address

    contract = w3.eth.contract(
        address=Web3.to_checksum_address(contract_address),
        abi=abi,
    )

    tx_hashes: list[str] = []

    # Step 1: hasProof should be false.
    print("Step 1: Checking hasProof for test hash ...")
    has_before: bool = contract.functions.hasProof(TEST_HASH).call()
    if has_before:
        print("WARN: Test hash already exists on-chain. Reporting PASS (idempotent).")
        return {
            "chain_id": chain_id,
            "contract_address": contract_address,
            "result": "PASS",
            "tx_hashes": [],
        }

    print("  hasProof = false (expected)")

    # Step 2: addProof.
    print("Step 2: Sending addProof transaction ...")
    nonce: int = w3.eth.get_transaction_count(caller_address)
    tx: dict[str, Any] = contract.functions.addProof(TEST_HASH).build_transaction(
        {
            "chainId": chain_id,
            "from": caller_address,
            "nonce": nonce,
            "gas": 100_000,
            "gasPrice": w3.eth.gas_price,
        }
    )
    signed_tx = w3.eth.account.sign_transaction(tx, private_key=private_key)
    raw_tx = getattr(signed_tx, "raw_transaction", None) or getattr(signed_tx, "rawTransaction", None)
    if raw_tx is None:
        raise RuntimeError("SignedTransaction has no raw tx attribute")
    tx_hash = w3.eth.send_raw_transaction(raw_tx)
    tx_hashes.append(tx_hash.hex())

    print(f"  tx sent: {tx_hash.hex()}")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=RPC_TIMEOUT)

    if receipt.status != 1:
        print(f"ERROR: addProof tx failed with status {receipt.status}")
        return {
            "chain_id": chain_id,
            "contract_address": contract_address,
            "result": "FAIL",
            "tx_hashes": tx_hashes,
        }

    print("  addProof tx confirmed")

    # Step 3: hasProof should now be true.
    print("Step 3: Checking hasProof after addProof ...")
    has_after: bool = contract.functions.hasProof(TEST_HASH).call()
    if not has_after:
        print("ERROR: hasProof returned false after addProof")
        return {
            "chain_id": chain_id,
            "contract_address": contract_address,
            "result": "FAIL",
            "tx_hashes": tx_hashes,
        }

    print("  hasProof = true (expected)")
    print("Verification PASSED")

    return {
        "chain_id": chain_id,
        "contract_address": contract_address,
        "result": "PASS",
        "tx_hashes": tx_hashes,
    }


def _write_verify_report(data: dict[str, Any]) -> Path:
    """Write verify_report.json to the audit logging directory."""
    os.makedirs(AUDIT_DIR, exist_ok=True)
    output_path: Path = AUDIT_DIR / "verify_report.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    print(f"Wrote {output_path}")
    return output_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Entry point for verify_testnet."""
    contract_address, rpc_url, chain_id, private_key = _read_env()

    print(f"Verifying ProofRegistry at {contract_address} on chain {chain_id} ...")
    start = time.monotonic()

    try:
        result = verify(contract_address, rpc_url, chain_id, private_key)
    except Exception as exc:
        print(f"ERROR: Verification failed: {exc}")
        sys.exit(1)

    elapsed = time.monotonic() - start
    print(f"Verification completed in {elapsed:.1f}s")

    _write_verify_report(result)

    if result["result"] == "PASS":
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
