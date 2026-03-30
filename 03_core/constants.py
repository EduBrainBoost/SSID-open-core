"""SSID Canonical Root Constants — Single Source of Truth for ROOT-24-LOCK.

This module is the ONE authoritative definition of CANONICAL_ROOTS.
Every other module MUST import from here instead of defining its own copy.

SoT v4.1.0 | ROOT-24-LOCK | Classification: Core Constants
"""

CANONICAL_ROOTS: frozenset[str] = frozenset({
    "01_ai_layer", "02_audit_logging", "03_core", "04_deployment",
    "05_documentation", "06_data_pipeline", "07_governance_legal",
    "08_identity_score", "09_meta_identity", "10_interoperability",
    "11_test_simulation", "12_tooling", "13_ui_layer", "14_zero_time_auth",
    "15_infra", "16_codex", "17_observability", "18_data_layer",
    "19_adapters", "20_foundation", "21_post_quantum_crypto", "22_datasets",
    "23_compliance", "24_meta_orchestration",
})

ROOT_COUNT = 24

# Convenience: sorted list form for modules that need ordered iteration
CANONICAL_ROOTS_LIST: list[str] = sorted(CANONICAL_ROOTS)

# Convenience: tuple form for modules that need indexing
CANONICAL_ROOTS_TUPLE: tuple[str, ...] = tuple(CANONICAL_ROOTS_LIST)
