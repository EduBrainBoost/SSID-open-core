#!/usr/bin/env python3
"""pqc_probe.py -- CLI tool to probe PQC engine capabilities.

Usage: python 12_tooling/cli/pqc_probe.py [--algorithm dilithium3]
"""

import argparse
import json
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))

from _21_post_quantum_crypto import pqc_engine  # noqa: E402


def probe(algorithm: str | None = None) -> dict:
    """Probe PQC engine for available algorithms and test keygen."""
    algos = pqc_engine.list_algorithms()
    result = {"algorithms": algos, "tests": []}
    targets = [algorithm] if algorithm else algos["signature"][:1]
    for alg in targets:
        try:
            kp = pqc_engine.generate_keypair(alg)
            result["tests"].append({"algorithm": alg, "status": "PASS", "keypair": kp})
        except Exception as exc:
            result["tests"].append({"algorithm": alg, "status": "FAIL", "error": str(exc)})
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe PQC engine")
    parser.add_argument("--algorithm", default=None, help="Specific algorithm to test")
    args = parser.parse_args()
    try:
        result = probe(args.algorithm)
    except ImportError:
        # Fallback if import path doesn't work
        result = {
            "algorithms": {
                "kem": ["CRYSTALS-Kyber-512", "CRYSTALS-Kyber-768", "CRYSTALS-Kyber-1024"],
                "signature": ["CRYSTALS-Dilithium2", "CRYSTALS-Dilithium3", "CRYSTALS-Dilithium5"],
            },
            "tests": [{"algorithm": "probe", "status": "STUB", "note": "Direct import unavailable"}],
        }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
