# ADR_0008_idempotent_structure_spec_generation

**Date:** 2026-02-16  
**Status:** Accepted  
**Type:** Technical Fix  

## Context

The `deterministic_repo_setup.py phase1` command was producing non-idempotent behavior. Running phase1 twice would mark `24_meta_orchestration/registry/structure_spec.json` as modified in git, even though the content was semantically identical.

## Root Cause

Line ending drift: The existing `structure_spec.json` file used CRLF (`\r\n`) line endings, while Python's `json.dumps()` produces LF (`\n`) line endings. The previous `write_json()` function compared text content, which failed to detect this byte-level difference.

## Decision

1. Modified `write_json()` function to compare bytes instead of text
2. Added `--check` flag (default): compares but does not write, exits 1 if drift detected
3. Added `--apply` flag: writes files only if content changed (idempotent mode)
4. Normalized `structure_spec.json` from CRLF to LF (canonical JSON format)

## Consequences

- `phase1` is now idempotent: running twice with `--apply` produces no changes
- Default behavior (`phase1` without `--apply`) is now check-only, exits 1 if drift detected
-structure_spec.json corrected to canonical UTF-8 with LF line endings

## Technical Details

- File: `12_tooling/scripts/deterministic_repo_setup.py`
- Lines modified: `write_json()` function, phase1 subparser
- No semantic changes to structure_spec.json content
