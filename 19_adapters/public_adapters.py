"""OpenCore public SDK — adapters reference."""
from __future__ import annotations
from .public_interface import AdapterContract


class IdentityAdapter(AdapterContract):
    """Public identity adapter (mock backend)."""

    def __init__(self) -> None:
        super().__init__("identity_adapter", "mock")

    def verify_did(self, did: str) -> dict:
        return {"did": did, "valid": True, "method": "mock_verification"}

    def resolve(self, did: str) -> dict:
        return {
            "id": did,
            "controller": "https://example.com",
            "publicKeys": [{"id": "key-1", "type": "Ed25519", "value": "synthetic-key"}],
        }


class MessagingAdapter(AdapterContract):
    """Public messaging adapter (mock backend)."""

    def __init__(self) -> None:
        super().__init__("messaging_adapter", "mock")

    def send(self, recipient: str, message: dict) -> dict:
        return {"message_id": "synthetic-msg-001", "status": "sent"}

    def receive(self, queue: str) -> list:
        return [{"message_id": "synthetic-msg-002", "body": {"text": "Hello world"}}]


class PaymentAdapter(AdapterContract):
    """Public payment adapter interface (mock backend, no real credentials)."""

    def __init__(self) -> None:
        super().__init__("payment_adapter", "mock")

    def calculate_fee(self, amount: float, currency: str = "USD") -> dict:
        return {
            "amount": amount,
            "currency": currency,
            "fee": amount * 0.02,
            "rate": 0.02,
        }

    def create_transaction(self, amount: float, recipient: str) -> dict:
        return {
            "transaction_id": "synthetic-tx-001",
            "amount": amount,
            "status": "pending",
        }
