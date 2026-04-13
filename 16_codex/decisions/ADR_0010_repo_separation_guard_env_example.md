# ADR-0010: Repo Separation Guard Exception for .env.example Files

## Context
The repo_separation_guard.py was forbidding all `.env.*` files, including safe template files like `.env.example` that should be tracked in version control. Additionally, root-level exceptions needed updates to reflect actual project directories.

## Decision
1. Modified `_matches_forbidden_glob()` to explicitly allow `.env.example` files while maintaining the ban on actual `.env` files
2. Updated `_iter_forbidden_glob_matches()` to skip `.env.example` files  
3. Updated `root_level_exceptions.yaml` to include all necessary directories and files

## Rationale
- `.env.example` files are safe to track as they contain no secrets
- Root-level exceptions must reflect the actual project structure for accurate validation
- These are necessary guardrail adjustments for Phase 5b gate runner execution

## Status
Accepted - Gate runner execution requires these relaxations

## Consequences
- Safe template files are now properly excluded from security checks
- Root structure validation can complete successfully
- No security regression (actual .env files still forbidden)
