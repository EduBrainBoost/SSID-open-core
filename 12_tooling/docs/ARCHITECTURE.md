# 12_tooling — Architecture

**Classification:** Public Specification
**SoT Version:** 4.1.0 | **Lock:** ROOT-24-LOCK

## Overview

This document describes the internal architecture of `12_tooling`.

## Directory Layout

```
12_tooling/
  README.md          — Module overview
  module.yaml        — Module metadata (version, deps)
  docs/              — Documentation & ADRs
    ARCHITECTURE.md  — This file
  src/               — Source code
  tests/             — Test suite (smoke + unit)
  shards/            — 16 domain shards (chart.yaml + manifest.yaml each)
```

## Shard Structure

Each shard follows the Hybrid-C convention:
- `chart.yaml` — Shard metadata and policy references
- `manifest.yaml` — Generated manifest (contracts, conformance, policies)
- `contracts/` — JSON Schema definitions (hash-only, no PII)
- `conformance/` — Validation fixtures and index
- `evidence/` — Evidence strategy (hash-only targets)

## Dependencies

See `module.yaml` for declared dependencies and version constraints.

## Invariants

- ROOT-24-LOCK: No new root directories may be created
- SAFE-FIX: No destructive operations
- PR-only: All changes via branch + PR + CI PASS
- Output contract: PASS/FAIL + Findings (no scores)
