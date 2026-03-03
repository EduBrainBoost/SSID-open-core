# ADR 0003: Root Dispatcher Removal and Root Hardening

## Status
Accepted

## Date
2026-02-11

## Context
Root-level governance requires a strict ROOT-24-LOCK layout with minimal exceptions.
The root wrapper `dispatcher.py` conflicted with the strict root policy and increased drift risk.
CI and local gates also had duplicated blocking steps.

## Decision
1. Remove root `dispatcher.py` and use `12_tooling/cli/ssid_dispatcher.py` as entry wrapper.
2. Keep canonical dispatcher implementation at `24_meta_orchestration/dispatcher/dispatcher.py`.
3. Minimize root exceptions in `23_compliance/exceptions/root_level_exceptions.yaml`.
4. Align CI to a single gate-chain entry (`python 12_tooling/cli/run_all_gates.py`) without a duplicate repo-separation step.

## Consequences
1. Root layout remains strict and deterministic.
2. Dispatcher invocation is centralized outside root.
3. CI/local parity is simplified at entry-point level.
4. No feature behavior is added; this is a structural and governance alignment change.
