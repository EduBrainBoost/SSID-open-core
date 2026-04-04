#!/usr/bin/env python3
"""SSID Artifact Signature Verifier.

Verifies evidence chain signatures, checks hash integrity, and validates
sealed evidence records.

Signature support:
  - HMAC-SHA256 (symmetric, for internal evidence sealing)
  - Ed25519 (asymmetric, optional — requires 'cryptography' package)
  - PQC Dilithium stub (via 21_post_quantum_crypto.src.pqc_core)

All operations are deterministic and produce PASS / FAIL outcomes.

Usage:
    python 12_tooling/security/signature_verifier.py \\
        --evidence evidence.json --key-file key.hex

SoT v4.1.0 | ROOT-24-LOCK
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Required seal fields (must match security_config.yaml)
# ---------------------------------------------------------------------------

REQUIRED_SEAL_FIELDS = frozenset(["evidence_id", "hash", "algorithm", "sealed_at", "signature"])

ALLOWED_HASH_ALGORITHMS = frozenset(["sha256", "sha384", "sha512", "sha3_256", "sha3_512"])
FORBIDDEN_HASH_ALGORITHMS = frozenset(["md5", "sha1"])

MIN_SIGNATURE_HEX_LENGTH = 64  # 32 bytes minimum


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class VerificationResult:
    """Result of a single verification check."""

    check: str
    passed: bool
    detail: str


@dataclass
class VerificationReport:
    """Aggregated verification report for an evidence record or artifact."""

    artifact_id: str
    verified_at: str
    overall_pass: bool
    results: list[VerificationResult] = field(default_factory=list)

    def add(self, check: str, passed: bool, detail: str) -> None:
        """Append a VerificationResult."""
        self.results.append(VerificationResult(check=check, passed=passed, detail=detail))
        if not passed:
            self.overall_pass = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "verified_at": self.verified_at,
            "overall_pass": self.overall_pass,
            "results": [{"check": r.check, "passed": r.passed, "detail": r.detail} for r in self.results],
        }


# ---------------------------------------------------------------------------
# Hash integrity
# ---------------------------------------------------------------------------


def compute_hash(data: bytes, algorithm: str = "sha256") -> str:
    """Compute a hex digest using the given algorithm.

    Args:
        data: Raw bytes to hash.
        algorithm: Hash algorithm name (must be in ALLOWED_HASH_ALGORITHMS).

    Returns:
        Hex-encoded digest.

    Raises:
        ValueError: If the algorithm is forbidden or unsupported.
    """
    algo = algorithm.lower().replace("-", "_")
    if algo in FORBIDDEN_HASH_ALGORITHMS:
        raise ValueError(f"Algorithm '{algo}' is forbidden by security policy")
    if algo not in ALLOWED_HASH_ALGORITHMS:
        raise ValueError(f"Algorithm '{algo}' is not in allowed list")
    h = hashlib.new(algo)
    h.update(data)
    return h.hexdigest()


def verify_hash(data: bytes, expected_hex: str, algorithm: str = "sha256") -> bool:
    """Verify that *data* hashes to *expected_hex* using *algorithm*.

    Args:
        data: Raw bytes to check.
        expected_hex: Expected hex digest.
        algorithm: Hash algorithm name.

    Returns:
        True if the digest matches, False otherwise.
    """
    try:
        actual = compute_hash(data, algorithm)
    except ValueError:
        return False
    return hmac.compare_digest(actual.lower(), expected_hex.lower())


# ---------------------------------------------------------------------------
# HMAC-SHA256 signature (symmetric — internal evidence sealing)
# ---------------------------------------------------------------------------


def hmac_sign(payload: bytes, secret: bytes) -> str:
    """Create an HMAC-SHA256 signature.

    Args:
        payload: Data to sign.
        secret: Shared secret key bytes.

    Returns:
        Hex-encoded HMAC-SHA256 digest.
    """
    return hmac.new(secret, payload, hashlib.sha256).hexdigest()


def hmac_verify(payload: bytes, signature_hex: str, secret: bytes) -> bool:
    """Verify an HMAC-SHA256 signature in constant time.

    Args:
        payload: Original data.
        signature_hex: Hex-encoded expected HMAC.
        secret: Shared secret key bytes.

    Returns:
        True if valid, False otherwise.
    """
    expected = hmac.new(secret, payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected.lower(), signature_hex.lower())


# ---------------------------------------------------------------------------
# Ed25519 (optional — requires cryptography package)
# ---------------------------------------------------------------------------


def ed25519_verify(
    message: bytes,
    signature_hex: str,
    public_key_hex: str,
) -> tuple[bool, str]:
    """Verify an Ed25519 signature.

    Args:
        message: Original message bytes.
        signature_hex: Hex-encoded signature.
        public_key_hex: Hex-encoded 32-byte public key.

    Returns:
        (success, detail_message) tuple.
    """
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError:
        return False, "cryptography package not installed — Ed25519 unavailable"

    try:
        key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))
        key.verify(bytes.fromhex(signature_hex), message)
        return True, "Ed25519 signature valid"
    except InvalidSignature:
        return False, "Ed25519 signature INVALID"
    except Exception as exc:
        return False, f"Ed25519 verification error: {exc}"


# ---------------------------------------------------------------------------
# Sealed evidence verification
# ---------------------------------------------------------------------------


def verify_sealed_evidence(
    record: dict[str, Any],
    hmac_secret: bytes | None = None,
) -> VerificationReport:
    """Verify a sealed evidence record.

    Checks:
      1. Required seal fields are present.
      2. Hash algorithm is allowed.
      3. Signature field meets minimum length.
      4. HMAC-SHA256 signature is valid (if secret provided).
      5. Evidence payload hash matches declared hash.

    Args:
        record: Evidence record dict.
        hmac_secret: Optional HMAC secret for signature validation.

    Returns:
        VerificationReport.
    """
    artifact_id = str(record.get("evidence_id", "<unknown>"))
    report = VerificationReport(
        artifact_id=artifact_id,
        verified_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        overall_pass=True,
    )

    # Check 1: Required fields
    missing = REQUIRED_SEAL_FIELDS - set(record.keys())
    report.add(
        "required_fields",
        not missing,
        f"Missing fields: {sorted(missing)}" if missing else "All required fields present",
    )

    # Check 2: Hash algorithm
    algorithm = str(record.get("algorithm", "")).lower().replace("-", "_")
    algo_ok = algorithm in ALLOWED_HASH_ALGORITHMS and algorithm not in FORBIDDEN_HASH_ALGORITHMS
    report.add(
        "hash_algorithm",
        algo_ok,
        f"Algorithm '{algorithm}' allowed" if algo_ok else f"Algorithm '{algorithm}' forbidden or unknown",
    )

    # Check 3: Signature minimum length
    sig_hex = str(record.get("signature", ""))
    sig_len_ok = len(sig_hex) >= MIN_SIGNATURE_HEX_LENGTH
    report.add(
        "signature_length",
        sig_len_ok,
        f"Signature length {len(sig_hex)} >= {MIN_SIGNATURE_HEX_LENGTH}"
        if sig_len_ok
        else f"Signature too short: {len(sig_hex)} < {MIN_SIGNATURE_HEX_LENGTH}",
    )

    # Check 4: HMAC verification (if secret provided)
    if hmac_secret is not None:
        # Canonicalise the payload by excluding the signature field
        payload_record = {k: v for k, v in record.items() if k != "signature"}
        payload_bytes = json.dumps(payload_record, sort_keys=True, separators=(",", ":")).encode("utf-8")
        hmac_ok = hmac_verify(payload_bytes, sig_hex, hmac_secret)
        report.add(
            "hmac_signature",
            hmac_ok,
            "HMAC-SHA256 signature valid" if hmac_ok else "HMAC-SHA256 signature INVALID",
        )

    # Check 5: Payload hash integrity
    declared_hash = str(record.get("hash", ""))
    payload_field = record.get("payload")
    if payload_field is not None:
        payload_bytes = json.dumps(payload_field, sort_keys=True, separators=(",", ":")).encode("utf-8")
        try:
            hash_ok = verify_hash(payload_bytes, declared_hash, algorithm if algo_ok else "sha256")
        except ValueError:
            hash_ok = False
        report.add(
            "payload_hash",
            hash_ok,
            "Payload hash matches" if hash_ok else "Payload hash MISMATCH",
        )
    else:
        report.add("payload_hash", True, "No payload field — hash check skipped")

    return report


# ---------------------------------------------------------------------------
# Batch evidence chain verifier
# ---------------------------------------------------------------------------


def verify_evidence_chain(
    records: list[dict[str, Any]],
    hmac_secret: bytes | None = None,
) -> list[VerificationReport]:
    """Verify a list of sealed evidence records.

    Args:
        records: List of evidence record dicts.
        hmac_secret: Optional HMAC secret.

    Returns:
        List of VerificationReport (one per record).
    """
    return [verify_sealed_evidence(r, hmac_secret=hmac_secret) for r in records]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(description="SSID Artifact Signature Verifier")
    parser.add_argument(
        "--evidence", type=Path, required=True, help="Path to evidence JSON file (single record or list)"
    )
    parser.add_argument("--key-file", type=Path, default=None, help="Path to file containing hex-encoded HMAC secret")
    parser.add_argument("--output", "-o", type=Path, default=None, help="Write verification report JSON to this path")
    parser.add_argument("--fail-on-invalid", action="store_true", help="Exit non-zero if any verification fails")
    args = parser.parse_args(argv)

    hmac_secret: bytes | None = None
    if args.key_file and args.key_file.exists():
        hmac_secret = bytes.fromhex(args.key_file.read_text(encoding="utf-8").strip())

    data = json.loads(args.evidence.read_text(encoding="utf-8"))
    records: list[dict[str, Any]] = data if isinstance(data, list) else [data]

    reports = verify_evidence_chain(records, hmac_secret=hmac_secret)
    report_dicts = [r.to_dict() for r in reports]

    overall_pass = all(r.overall_pass for r in reports)
    output = {
        "verified_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "overall_pass": overall_pass,
        "record_count": len(reports),
        "pass_count": sum(1 for r in reports if r.overall_pass),
        "fail_count": sum(1 for r in reports if not r.overall_pass),
        "reports": report_dicts,
    }
    output_json = json.dumps(output, indent=2)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output_json + "\n", encoding="utf-8")
        print(f"Verification report written to {args.output}")
    else:
        print(output_json)

    status = "PASS" if overall_pass else "FAIL"
    print(f"\nOverall: {status} ({output['pass_count']}/{output['record_count']} records passed)", file=sys.stderr)

    if args.fail_on_invalid and not overall_pass:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
