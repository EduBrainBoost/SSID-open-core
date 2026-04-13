# ADR-0075: Root-Level Build Configuration Exceptions

**Status:** Accepted
**Date:** 2026-03-28
**Decision:** Allow `conftest.py` and `pyproject.toml` at repository root as build/test infrastructure exceptions.

## Context

ROOT-24-LOCK requires that only canonical root directories (01_-24_) and explicitly allowed files exist at the repository root level. The existing exception list (per `23_compliance/exceptions/root_level_exceptions.yaml`) allows `pytest.ini` but does not cover `conftest.py` or `pyproject.toml`.

Both files are standard Python build/test infrastructure:
- `conftest.py`: pytest fixture configuration, required at root for cross-root test discovery
- `pyproject.toml`: PEP 517/518 build system declaration, required for `pip install -e .`

## Decision

Add `conftest.py` and `pyproject.toml` to the root-level exception allowlist in `23_compliance/exceptions/root_level_exceptions.yaml`.

**Rationale:**
- Both are standard Python ecosystem files that tools expect at project root
- Moving them would break pytest discovery and pip/setuptools workflows
- They contain no business logic, only build/test configuration
- `pytest.ini` is already allowed — `conftest.py` serves the same role

## Consequences

- `conftest.py` and `pyproject.toml` are now explicitly allowed at root
- Structure guard and ROOT-24-LOCK checks must not flag them
- This does NOT set a precedent for other root-level files
