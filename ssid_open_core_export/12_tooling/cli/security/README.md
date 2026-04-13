# SSID Security Infrastructure

This directory contains security scanning, auditing, and validation tools for the SSID repository.

## Overview

The security infrastructure includes:
- **Secret Scanning**: Detects leaked credentials, API keys, tokens
- **Dependency Audit**: Checks for known CVEs and vulnerabilities
- **SBOM Generation**: Creates Software Bill of Materials (CycloneDX format)
- **Attestation**: Generates build provenance and integrity attestations
- **CI Integration**: Automated gates on every push and PR

## Security Tools

### Secret Scanning (`secret_scan.py`)

Detects potentially leaked credentials with pattern matching.

**Patterns detected:**
- AWS access keys (AKIA...)
- GitHub tokens (ghp_, gho_, ghu_)
- Private keys (RSA, DSA, EC, OpenSSH, PGP)
- Database URIs (MongoDB, Postgres, MySQL, Redis)
- API keys, passwords, JWT tokens, Slack tokens, Stripe keys

**Exclusions:**
- Worktrees and agent runs
- Test fixtures and cache directories
- Build artifacts
- Known test placeholders (configured in gitleaks.toml)

**Usage:**
```bash
python security/secret_scan.py
```

**Output:** `security/secrets-scan.json`

### Dependency Audit (`dependency_audit.py`)

Scans installed Python packages for known vulnerabilities.

**Features:**
- Checks 160+ installed packages
- Reports CVEs and security issues
- Validates package licenses
- Version comparison against known vulnerable patterns

**Usage:**
```bash
python security/dependency_audit.py
```

**Output:** `security/dependency-audit.json`

## Supply Chain Security

### Software Bill of Materials (SBOM)

The repository maintains a CycloneDX-compliant SBOM documenting all dependencies.

**Files:**
- `sbom/sbom.json` - Full SBOM in CycloneDX 1.4 format
- `sbom/manifest.json` - SBOM metadata and summary
- `sbom/sbom_generator.py` - Generator script

**Current Components:**
- pytest 9.0.2 (MIT)
- pyyaml 6.0.1 (MIT)
- jsonschema 4.21.1 (MIT)
- pydantic 2.5.0 (MIT)
- jinja2 3.1.2 (BSD-3-Clause)

**Generation:**
```bash
python sbom/sbom_generator.py
```

### Build Attestations

Build attestations prove how artifacts were built and trace them back to source.

**Files:**
- `attestations/build-attestation.json` - Build environment and materials
- `attestations/provenance-attestation.json` - SLSA v0.2 provenance
- `attestations/summary.json` - Attestation metadata

**Included Information:**
- Git commit and branch information
- Build environment (Python version, OS, user)
- Source materials and their hashes
- Build invocation details
- Reproducibility flag

**Generation:**
```bash
python attestations/attestation_generator.py
```

**Production Signing:**
```bash
cosign sign-blob --key ~/.ssid/build-key.pem attestations/build-attestation.json
```

## CI Integration

### GitHub Actions Workflow

Security gates are integrated into `.github/workflows/ssid_ci.yml`:

1. **Secret Scan (Gitleaks)** - Runs on every push and PR
   - Detects secrets using gitleaks
   - Config: `23_compliance/gitleaks.toml`
   - Blocks merge if secrets found

2. **Test Suite** - 1059+ tests across:
   - Unit tests
   - Integration tests
   - E2E tests
   - Compliance tests
   - Autorunner tests

3. **Evidence Verification** - Validates audit trail
   - Agent run documentation
   - Report events
   - Evidence chain integrity

## Test Coverage

The SSID repository includes comprehensive test coverage:

**Test Distribution:**
- Unit tests: 45 files
- Integration tests: 28 files
- E2E tests: 15 files
- Compliance tests: 350+ tests
- Autorunner tests: 78 tests

**Coverage Target:** 80%+

**Running Tests:**
```bash
# All tests
pytest -v

# Unit tests only
pytest tests/unit/ -v

# Integration tests only
pytest tests/integration/ -v

# E2E tests only
pytest tests/e2e/ -v

# With coverage report
pytest --cov=src --cov-report=html
```

## Security Report

The comprehensive security report is available at:
- `security/security-report.json`

**Report includes:**
- Test coverage statistics
- Secret scan results
- Dependency audit findings
- SBOM summary
- Attestation status
- CI gate status
- Compliance summary

## Best Practices

### Local Development

1. **Pre-commit scanning:**
   ```bash
   # Before committing, run secret scan
   python security/secret_scan.py
   ```

2. **Test locally:**
   ```bash
   # Run all tests before pushing
   pytest -v
   ```

3. **Check dependencies:**
   ```bash
   # Update SBOM before release
   python sbom/sbom_generator.py
   ```

### CI/CD Integration

1. **Every commit:**
   - Secret scanning (gitleaks)
   - Test suite execution
   - Lint and format checks

2. **Before merge:**
   - All tests passing
   - No secrets detected
   - Evidence chain complete

3. **On release:**
   - Sign attestations with build key
   - Upload SBOM to artifact registry
   - Create release notes with security summary

## Troubleshooting

### Secret Scan False Positives

If the secret scan detects false positives:

1. Identify the pattern in `secret_scan.py`
2. Add file/path to EXCLUDE_PATTERNS
3. For legitimate test cases, add commit to `23_compliance/gitleaks.toml`

**Example:**
```python
# In secret_scan.py
EXCLUDE_PATTERNS = [
    r"test_secret_examples\.py",  # Contains intentional test tokens
    r"docs/examples/.*\.yaml",     # Documentation examples
]
```

### Dependency Vulnerabilities

If vulnerabilities are found:

1. Update package: `pip install --upgrade package-name`
2. Regenerate SBOM: `python sbom/sbom_generator.py`
3. Update KNOWN_VULNERABILITIES in `dependency_audit.py`
4. Create PR with security fix

### Test Failures

1. Check specific test: `pytest -v tests/unit/test_name.py`
2. Review error message and stack trace
3. Fix test or code as needed
4. Re-run full test suite: `pytest -v`

## Security References

- **CycloneDX:** https://cyclonedx.org/
- **SLSA Framework:** https://slsa.dev/
- **Gitleaks:** https://github.com/gitleaks/gitleaks
- **OWASP:** https://owasp.org/

## Contact

For security issues:
1. Do NOT open public issues for security vulnerabilities
2. Contact security team directly
3. Follow responsible disclosure guidelines

## Maintenance

- **Update frequency:** Security tools updated monthly
- **SBOM refresh:** On every release
- **Attestation signing:** Before production deployments
- **Test suite expansion:** Continuous improvement

---

**Last Updated:** 2026-03-17
**Status:** ACTIVE
