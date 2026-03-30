"""Deploy the ProofRegistry contract to a testnet.

Reads RPC_URL, CHAIN_ID, and PRIVATE_KEY from environment variables.
Writes deployment.json to the audit logging directory on success.
Never logs or prints secret values.

Exit code 0 on success, 1 on failure.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

try:
    from web3 import Web3
except ImportError:
    print("ERROR: web3 package is not installed. Run: pip install web3")
    sys.exit(1)

__all__ = ["deploy", "load_contract_artifacts", "redact_address"]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT: Path = Path(__file__).resolve().parents[4]
CONTRACTS_DIR: Path = (
    REPO_ROOT
    / "12_tooling"
    / "testnet_mvp"
    / "01_hash_only_proof_registry"
    / "contracts"
)
AUDIT_DIR: Path = (
    REPO_ROOT
    / "02_audit_logging"
    / "agent_runs"
    / "PH3_IMPL_SCRIPTS_002"
)
ABI_PATH: Path = CONTRACTS_DIR / "proof_registry_abi.json"
BYTECODE_PATH: Path = CONTRACTS_DIR / "proof_registry_bytecode.json"

# Deterministic timeout for all RPC calls (seconds).
RPC_TIMEOUT: int = 120


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def redact_address(addr: str) -> str:
    """Mask an address keeping only the first 6 and last 4 characters.

    Example: ``0xAbCdEf1234567890...7890`` -> ``0xAbCd...7890``
    """
    if len(addr) <= 10:
        return addr
    return f"{addr[:6]}...{addr[-4:]}"


def _read_env() -> Tuple[str, int, str]:
    """Read required environment variables. Exits on missing values."""
    rpc_url: Optional[str] = os.environ.get("RPC_URL")
    chain_id_str: Optional[str] = os.environ.get("CHAIN_ID")
    private_key: Optional[str] = os.environ.get("PRIVATE_KEY")

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


def load_contract_artifacts() -> Tuple[list, str]:
    """Load ABI and bytecode from the contracts directory.

    Returns:
        Tuple of (abi, bytecode_hex).
    """
    with open(ABI_PATH, "r", encoding="utf-8") as f:
        abi: list = json.load(f)

    with open(BYTECODE_PATH, "r", encoding="utf-8") as f:
        bytecode_data: Dict[str, Any] = json.load(f)

    bytecode_hex: str = bytecode_data.get("bytecode") or bytecode_data.get("object", "")
    if not bytecode_hex:
        raise ValueError(
            f"No bytecode found in {BYTECODE_PATH}: "
            "expected key 'bytecode' or 'object'"
        )
    return abi, bytecode_hex


# ---------------------------------------------------------------------------
# Core deploy function
# ---------------------------------------------------------------------------


def deploy(
    rpc_url: str,
    chain_id: int,
    private_key: str,
) -> Dict[str, Any]:
    """Deploy ProofRegistry and return deployment metadata.

    Args:
        rpc_url: JSON-RPC endpoint URL.
        chain_id: Target chain ID.
        private_key: Deployer private key (hex string).

    Returns:
        Dict with contract_address, tx_hash, chain_id, deployer (redacted).

    Raises:
        RuntimeError: On deployment failure.
    """
    abi, bytecode_hex = load_contract_artifacts()

    w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": RPC_TIMEOUT}))

    if not w3.is_connected():
        raise RuntimeError("Cannot connect to RPC endpoint")

    account = w3.eth.account.from_key(private_key)
    deployer_address: str = account.address
    print(f"Deployer: {redact_address(deployer_address)} (full for faucet: {deployer_address})")

    balance = w3.eth.get_balance(deployer_address)
    print(f"Balance: {w3.from_wei(balance, 'ether')} POL")
    if balance == 0:
        raise RuntimeError(
            f"Deployer {deployer_address} has zero balance on chain {chain_id}. "
            "Fund via faucet before deploying."
        )

    contract = w3.eth.contract(abi=abi, bytecode=bytecode_hex)

    nonce: int = w3.eth.get_transaction_count(deployer_address)

    tx: Dict[str, Any] = contract.constructor().build_transaction(
        {
            "chainId": chain_id,
            "from": deployer_address,
            "nonce": nonce,
            "gas": 500_000,
            "gasPrice": w3.eth.gas_price,
        }
    )

    signed_tx = w3.eth.account.sign_transaction(tx, private_key=private_key)
    raw_tx = getattr(signed_tx, "raw_transaction", None) or getattr(signed_tx, "rawTransaction", None)
    if raw_tx is None:
        raise RuntimeError("SignedTransaction has no raw tx attribute")
    tx_hash = w3.eth.send_raw_transaction(raw_tx)

    print(f"Deploy tx sent: {tx_hash.hex()}")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=RPC_TIMEOUT)

    if receipt.status != 1:
        raise RuntimeError(f"Deploy tx failed with status {receipt.status}")

    contract_address: str = receipt.contractAddress
    print(f"Contract deployed at: {contract_address}")

    result: Dict[str, Any] = {
        "chain_id": chain_id,
        "contract_address": contract_address,
        "deployer": redact_address(deployer_address),
        "tx_hash": tx_hash.hex(),
    }
    return result


def _write_deployment_json(data: Dict[str, Any]) -> Path:
    """Write deployment.json to the audit logging directory."""
    os.makedirs(AUDIT_DIR, exist_ok=True)
    output_path: Path = AUDIT_DIR / "deployment.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    print(f"Wrote {output_path}")
    return output_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Entry point for deploy_testnet."""
    rpc_url, chain_id, private_key = _read_env()

    print(f"Deploying ProofRegistry to chain {chain_id} ...")
    start = time.monotonic()

    try:
        result = deploy(rpc_url, chain_id, private_key)
    except Exception as exc:
        print(f"ERROR: Deployment failed: {exc}")
        sys.exit(1)

    elapsed = time.monotonic() - start
    print(f"Deployment completed in {elapsed:.1f}s")

    _write_deployment_json(result)
    sys.exit(0)


if __name__ == "__main__":
    main()
