#!/usr/bin/env python3
"""
verify_testnet.py — Round-trip verification of a deployed ProofRegistry contract.

Verification flow:
  1. hasProof(TEST_HASH) == false  (proof not yet on-chain)
  2. addProof(TEST_HASH)           (send transaction)
  3. hasProof(TEST_HASH) == true   (proof now confirmed)

All secrets are read exclusively from environment variables. No credentials,
private keys, or RPC URLs are ever printed, logged, or persisted to disk.

Environment variables (required):
  CONTRACT_ADDRESS — Deployed ProofRegistry address
  RPC_URL          — JSON-RPC endpoint
  CHAIN_ID         — Integer chain identifier
  PRIVATE_KEY      — Caller private key in hex (0x-prefixed or raw)

Output:
  Writes verify_report.json to 02_audit_logging/agent_runs/PH3_VERIFY_SCRIPT_001/
  verify_report.json contains: result (PASS/FAIL), tx_hashes, chain_id, contract_address

Exit codes:
  0  — Verification PASS
  1  — Verification FAIL or error
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

_REPO_ROOT: Path = Path(__file__).resolve().parents[2]

CONTRACTS_DIR: Path = _REPO_ROOT / "24_meta_orchestration" / "contracts"
AUDIT_DIR: Path = _REPO_ROOT / "02_audit_logging" / "agent_runs" / "PH3_VERIFY_SCRIPT_001"
ABI_PATH: Path = CONTRACTS_DIR / "proof_registry_abi.json"

# Deterministic timeout for all RPC calls (seconds). No infinite waits.
RPC_TIMEOUT: int = 120

# Gas limit for addProof transaction
ADD_PROOF_GAS_LIMIT: int = 100_000

# Canonical test hash: SHA-256 of b"ssid-testnet-verify" as bytes32.
# This value is deterministic and reproducible. Same hash every run.
TEST_HASH: bytes = hashlib.sha256(b"ssid-testnet-verify").digest()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_env() -> tuple[str, str, int, str]:
    """Read required environment variables. Exits with code 1 on missing values.

    Returns:
        Tuple of (contract_address, rpc_url, chain_id, private_key).
        private_key is never logged or persisted.
    """
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
        print(f"ERROR: CHAIN_ID must be an integer, got: {chain_id_str!r}")
        sys.exit(1)

    return (
        contract_address,  # type: ignore[return-value]
        rpc_url,  # type: ignore[return-value]
        chain_id,
        private_key,  # type: ignore[return-value]
    )


def _load_abi() -> list:
    """Load the ProofRegistry ABI from the canonical contracts directory.

    Returns:
        Parsed ABI list.

    Raises:
        FileNotFoundError: If the ABI file does not exist.
    """
    if not ABI_PATH.exists():
        raise FileNotFoundError(f"ABI file not found: {ABI_PATH}")
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
    """Run the canonical round-trip verification against a deployed ProofRegistry.

    Steps:
        1. hasProof(TEST_HASH) == false  — proof must not exist yet
        2. addProof(TEST_HASH)           — write proof to chain
        3. hasProof(TEST_HASH) == true   — proof must now exist

    If the proof already exists on-chain (idempotent re-run), returns PASS
    without attempting to add it again.

    Args:
        contract_address: Deployed ProofRegistry address.
        rpc_url: JSON-RPC endpoint URL (never logged).
        chain_id: Target chain ID.
        private_key: Caller private key (never logged or stored).

    Returns:
        Dict containing:
          - result: "PASS" or "FAIL"
          - tx_hashes: List of transaction hashes (may be empty on idempotent PASS)
          - chain_id: Chain identifier
          - contract_address: Contract address (not a secret)
    """
    abi = _load_abi()
    w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": RPC_TIMEOUT}))

    if not w3.is_connected():
        print("ERROR: Cannot connect to RPC endpoint.")
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

    # Step 1: hasProof must be false (fresh state).
    print("Step 1: hasProof(TEST_HASH) — expecting false ...")
    try:
        has_before: bool = contract.functions.hasProof(TEST_HASH).call()
    except Exception as exc:
        print(f"ERROR: hasProof call failed: {exc}")
        return {
            "chain_id": chain_id,
            "contract_address": contract_address,
            "result": "FAIL",
            "tx_hashes": tx_hashes,
        }

    if has_before:
        # Idempotent: proof was already added (previous run). Still PASS.
        print("  WARN: Test hash already exists on-chain. Idempotent PASS.")
        return {
            "chain_id": chain_id,
            "contract_address": contract_address,
            "result": "PASS",
            "tx_hashes": [],
        }
    print("  hasProof = false (OK)")

    # Step 2: addProof(TEST_HASH).
    print("Step 2: addProof(TEST_HASH) — sending transaction ...")
    try:
        nonce: int = w3.eth.get_transaction_count(caller_address)
        tx: dict[str, Any] = contract.functions.addProof(TEST_HASH).build_transaction(
            {
                "chainId": chain_id,
                "from": caller_address,
                "nonce": nonce,
                "gas": ADD_PROOF_GAS_LIMIT,
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
    except Exception as exc:
        print(f"ERROR: addProof tx failed: {exc}")
        return {
            "chain_id": chain_id,
            "contract_address": contract_address,
            "result": "FAIL",
            "tx_hashes": tx_hashes,
        }

    if receipt.status != 1:
        print(f"ERROR: addProof tx reverted with status {receipt.status}")
        return {
            "chain_id": chain_id,
            "contract_address": contract_address,
            "result": "FAIL",
            "tx_hashes": tx_hashes,
        }
    print("  addProof tx confirmed")

    # Step 3: hasProof must now be true.
    print("Step 3: hasProof(TEST_HASH) — expecting true ...")
    try:
        has_after: bool = contract.functions.hasProof(TEST_HASH).call()
    except Exception as exc:
        print(f"ERROR: hasProof post-add call failed: {exc}")
        return {
            "chain_id": chain_id,
            "contract_address": contract_address,
            "result": "FAIL",
            "tx_hashes": tx_hashes,
        }

    if not has_after:
        print("ERROR: hasProof returned false after addProof (state not committed)")
        return {
            "chain_id": chain_id,
            "contract_address": contract_address,
            "result": "FAIL",
            "tx_hashes": tx_hashes,
        }

    print("  hasProof = true (OK)")
    print("Verification PASS")

    return {
        "chain_id": chain_id,
        "contract_address": contract_address,
        "result": "PASS",
        "tx_hashes": tx_hashes,
    }


def _write_verify_report(data: dict[str, Any]) -> Path:
    """Write verify_report.json to the audit logging directory.

    The output file contains NO secrets: no private keys, no RPC URLs.

    Args:
        data: Verification result dict.

    Returns:
        Path to the written verify_report.json file.
    """
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    output_path: Path = AUDIT_DIR / "verify_report.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    print(f"Wrote verify_report.json to {output_path.relative_to(_REPO_ROOT)}")
    return output_path


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point for verify_testnet.py.

    Reads ENV, runs verification round-trip, writes verify_report.json.
    Exits 0 on PASS, 1 on FAIL or error.
    """
    contract_address, rpc_url, chain_id, private_key = _read_env()
    print(f"Verifying ProofRegistry at {contract_address} on chain {chain_id} ...")
    start = time.monotonic()

    try:
        result = verify(contract_address, rpc_url, chain_id, private_key)
    except Exception as exc:
        print(f"ERROR: Verification raised unexpected exception: {exc}")
        sys.exit(1)

    elapsed = time.monotonic() - start
    print(f"Verification completed in {elapsed:.1f}s")
    _write_verify_report(result)

    sys.exit(0 if result["result"] == "PASS" else 1)


if __name__ == "__main__":
    main()
