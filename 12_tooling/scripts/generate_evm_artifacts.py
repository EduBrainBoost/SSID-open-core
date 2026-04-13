#!/usr/bin/env python3
"""generate_evm_artifacts.py -- Generates/validates EVM spec and ABI artifacts.

Validates that:
  - ABI JSON files parse correctly.
  - Spec files exist alongside ABIs.
  - fee_split_invariants.yaml parses correctly.
"""
import json
import pathlib
import sys

import yaml

REPO = pathlib.Path(__file__).resolve().parents[2]
EVM_DIR = REPO / "16_codex" / "contracts" / "evm"

REQUIRED_FILES = [
    "reward_treasury_spec.md",
    "license_fee_router_spec.md",
    "reward_treasury_abi.json",
    "license_fee_router_abi.json",
    "fee_split_invariants.yaml",
]


def main() -> int:
    errors = []
    for fname in REQUIRED_FILES:
        fpath = EVM_DIR / fname
        if not fpath.is_file():
            errors.append(f"MISSING: {fname}")
            continue

        if fname.endswith(".json"):
            try:
                data = json.loads(fpath.read_text(encoding="utf-8"))
                if not isinstance(data, list):
                    errors.append(f"INVALID: {fname} is not a JSON array")
                else:
                    print(f"PASS: {fname} ({len(data)} entries)")
            except json.JSONDecodeError as exc:
                errors.append(f"PARSE_ERROR: {fname}: {exc}")

        elif fname.endswith(".yaml"):
            try:
                data = yaml.safe_load(fpath.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    errors.append(f"INVALID: {fname} is not a YAML dict")
                else:
                    print(f"PASS: {fname}")
            except yaml.YAMLError as exc:
                errors.append(f"PARSE_ERROR: {fname}: {exc}")

        else:
            print(f"PASS: {fname} (exists)")

    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        return 1

    print("All EVM artifacts validated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
