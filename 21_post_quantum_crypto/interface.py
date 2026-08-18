"""OpenCore public SDK — post-quantum crypto interfaces."""
from __future__ import annotations
import hashlib


class CryptoAgilityInterface:
    """Public post-quantum crypto agility interface."""

    SUPPORTED_ALGORITHMS = [
        "ML-DSA-44",      # NIST PQC Digital Signature
        "ML-DSA-64",      # NIST PQC Digital Signature
        "ML-DSA-87",      # NIST PQC Digital Signature
        "ML-KEM-512",     # NIST PQC Key Encapsulation
        "ML-KEM-768",     # NIST PQC Key Encapsulation
        "ML-KEM-1024",    # NIST PQC Key Encapsulation
        "SLH-DSA-SHA2-128f",  # NIST PQC Stateful Hash
    ]

    def list_algorithms(self) -> list:
        return self.SUPPORTED_ALGORITHMS

    def hash(self, data: bytes) -> str:
        """Public hash function example."""
        return hashlib.sha3_256(data).hexdigest()

    def benchmark(self, algorithm: str) -> dict:
        """Return synthetic benchmark data (not real production benchmarks)."""
        return {
            "algorithm": algorithm,
            "key_generation_us": 150.5,
            "sign_us": 200.3,
            "verify_us": 180.7,
            "synthetic": True,
            "note": "Benchmark values are illustrative, not production-grade",
        }

    def migration_path(self) -> dict:
        return {
            "current": "ECDSA-P256",
            "target": "ML-DSA-64",
            "hybrid_option": "ML-DSA-64 + ECDSA-P256",
            "recommended_timeline": "2026-2030",
        }
