# SSID Community Guidelines (Enterprise)

## Scope

These guidelines govern contributions to the SSID repository and all associated
enterprise modules. They apply to all contributors: human maintainers, AI agents,
and automated CI systems.

## Core Principles

### 1. Structural Integrity First
- The 24-root architecture (ROOT-24-LOCK) is immutable
- No contribution may add, remove, or rename root modules
- Every file must reside within an authorized root or an explicitly excepted path

### 2. Non-Custodial by Design
- No personally identifiable information (PII) may be stored in any file
- All identity references use SHA3-256 hashes
- No credentials, API keys, or private keys in any committed file

### 3. Additive-Only Changes (SAFE-FIX)
- All writes must be accompanied by SHA256 before/after evidence
- Destructive changes (deletions, overwrites) require explicit approval
- Evidence logs are immutable once written to WORM storage

### 4. Transparency and Traceability
- Every change must be traceable to a session, agent, and approval
- AI-generated code must be marked with Co-Authored-By attribution
- No "stealth commits" — all changes go through PR review

## Contribution Workflow

1. **Fork/Branch**: Create a feature or fix branch from `main`
2. **Scope Check**: Verify your changes fall within an authorized root
3. **Structure Guard**: Run `bash 12_tooling/scripts/structure_guard.sh` locally
4. **Tests**: Run relevant tests in `11_test_simulation/`
5. **PR**: Create a pull request with clear description
6. **Review**: Await CODEOWNERS review per maintainer tier
7. **Merge**: Only after CI gates pass and approval is granted

## Prohibited Actions

- Committing directly to `main` without PR
- Bypassing CI gates with `--no-verify`
- Adding dependencies without security review
- Storing secrets in any file (use Vault integration)
- Creating new root-level directories

## Reporting Issues

- Security vulnerabilities: follow responsible disclosure via SECURITY.md
- Structural violations: file an issue with label `structure-violation`
- Policy questions: discuss in governance channel before implementing
