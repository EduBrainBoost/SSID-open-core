# SSID Open-Core Compliance Framework

## Overview

SSID Open-Core is designed to comply with major international regulatory frameworks while maintaining non-custodial, privacy-preserving principles. This document outlines the regulatory alignment, compliance mechanisms, and how external integrators can meet their own compliance obligations.

## Regulatory Frameworks

### GDPR (General Data Protection Regulation)

**Applicability**: EU-based deployments and organizations processing EU resident data.

**SSID Compliance**:
- **Data Minimization**: No PII stored on-chain; only cryptographic proofs (SHA256 hashes)
- **Purpose Limitation**: Identity verification proofs limited to specified verification purposes
- **Consent Management**: External systems responsible for user consent collection
- **Right to be Forgotten**: Users control identity lifecycle; deletion triggers proof revocation
- **Data Processing Agreements**: Available upon request for enterprise deployments

**External Integrator Obligations**:
```python
from ssid_open_core.compliance import validate_processing

compliance = validate_processing(
    user_id="user_hash",
    data_types=["identity"],
    purposes=["authentication"],
    jurisdiction="EU"
)

if not compliance.compliant:
    log_violation(compliance.gaps)
    request_consent_update()
```

### eIDAS 2.0 (Electronic Identification, Authentication and Trust Services)

**Applicability**: Digital identity systems in EU, qualified signature requirements.

**SSID Compliance**:
- **Trust Service Qualification**: SSID proofs compatible with qualified trust services
- **Authentication Strength**: Multi-factor verification supported
- **Digital Signatures**: Integration with eSignature providers (KILT, SignMe, Namirial)
- **Trust Framework**: Non-custodial model aligns with distributed trust principles

**Compliance Level**: eIDAS-ready for qualified signature workflows

### MiCA (Markets in Crypto-Assets)

**Applicability**: EU crypto-asset regulation; if SSID tokens used in secondary market.

**SSID Compliance**:
- **Non-Custodial Architecture**: No asset custody on platform
- **Token Distancing**: SSID system tokens separate from governance tokens
- **Fee Transparency**: 3% system, 1% developer, 2% pool allocation disclosed
- **Sanctions Screening**: External systems responsible for AML/CFT
- **Market Integrity**: Smart contracts enforce governance rules

**Integration Notes**:
- SSID enables identity verification for MiCA-required KYC/AML
- Not a custodial trading platform; suitable for DeFi integration

### GDPR Data Protection Impact Assessment (DPIA)

**Areas Addressed**:
- **Processing Scope**: Limited to cryptographic proof verification
- **Storage Principle**: Hash-only; no plaintext PII
- **Access Control**: Cryptographic validation prevents unauthorized access
- **Data Retention**: User-controlled; no mandatory retention beyond proof lifecycle
- **Privacy by Design**: Zero-knowledge proof architecture (future roadmap)

### EU AI Act Compliance

**Scope**: Where SSID scoring or ML-based identity verification integrated.

**Requirements**:
- **Risk Assessment**: AI-driven identity scoring undergoes conformity assessment
- **Transparency**: AI decision factors documented for users
- **Bias Auditing**: Quarterly bias audits for ML components (21_post_quantum_crypto + 01_ai_layer)
- **Human Oversight**: Final identity decisions retain human review option

## Compliance Levels

SSID Open-Core supports tiered compliance levels for different deployment contexts:

### Level 1: Basic Compliance

**Scope**: General terms, minimal regulatory requirements.

**Use Cases**:
- Testnet deployments
- Development and testing
- Non-regulated identity proofs

**Configuration**:
```python
validator = ComplianceValidator(jurisdiction="NONE", level="level_1_basic")
```

### Level 2: GDPR

**Scope**: EU data protection standards.

**Use Cases**:
- EU consumer identity verification
- Data minimization requirements
- Consent-based processing

**Requirements**:
- Hash-only storage (enforced)
- Consent logging
- Data processing agreements
- 90-day retention maximum

**Configuration**:
```python
validator = ComplianceValidator(jurisdiction="EU", level="level_2_gdpr")
compliance = validator.check_compliance(
    user_data_handling="hash_only",
    retention_period_days=90,
    pii_storage="none"
)
```

### Level 3: eIDAS

**Scope**: Qualified digital identity and signature services.

**Use Cases**:
- Digital identity issuance
- Qualified signature generation
- Cross-border EU identity services

**Requirements**:
- eIDAS-compatible identity proofs
- Qualified trust service provider integration
- Signature validation chains
- Non-repudiation guarantees

**Configuration**:
```python
validator = ComplianceValidator(jurisdiction="EU", level="level_3_eidas")
```

### Level 4: MiCA + Full Regulatory

**Scope**: Crypto-asset market regulation + all above.

**Use Cases**:
- Regulated crypto exchange identity
- Institutional custody identity verification
- Cross-border digital asset settlement

**Requirements**:
- All Level 3 + GDPR + eIDAS
- MiCA-compliant KYC/AML
- Sanctions screening integration
- Market surveillance capability

**Configuration**:
```python
validator = ComplianceValidator(jurisdiction="EU", level="level_4_mica")
```

## Privacy Architecture

### Hash-Only Proofs

SSID never stores plaintext PII. All identity verification uses cryptographic hashes:

```
User ID: john.doe@example.com
Hash: SHA256(john.doe@example.com) = 4a7d1ed...
On-Chain Storage: 4a7d1ed... (only)
PII Location: External (user's wallet, KYC provider)
```

**Privacy Guarantee**: Platform cannot be subpoenaed for PII because it has no PII.

### Zero-Knowledge Architecture

Future phases implement zero-knowledge proofs to enable verification without proof data exposure:

- **ZK-SNARK Implementation**: Proving identity without revealing details
- **Selective Disclosure**: User controls what attributes revealed to verifier
- **Pseudonymity**: Multiple identities per individual possible

### Data Minimization

Only data required for verification is transmitted:

```python
proof_data = {
    "identity_hash": "0x...",           # Required
    "proof_signature": "0x...",         # Required
    "timestamp": 1234567890,            # Required
    "kycProvider": "didit"              # Required
    # NO: email, name, address, etc.
}
```

## Audit & Compliance Verification

### Compliance Validators

`23_compliance/validators/` contains automated compliance checkers:

```python
from ssid_open_core.compliance import runtime_checker

# Real-time validation during operation
violations = runtime_checker.check(
    operation="identity_verify",
    parameters=proof_data,
    jurisdiction="EU"
)

if violations:
    raise ComplianceViolationError(violations)
```

### Evidence Collection

All compliance-related operations logged to immutable evidence store:

- **Operation Timestamp**: When proof verified
- **Identity Hash**: What was verified (not PII)
- **Compliance Status**: PASS/FAIL per jurisdiction
- **Evidence Hash**: SHA256 of entire event

### Audit Trail

Accessible via compliance API:

```
GET /api/v1/compliance/report
    ↓
Returns: Audit evidence for specified date range
Format: JSON with timestamps, hashes, status
```

### Compliance Metrics

Key performance indicators tracked:

| Metric | Target | Definition |
|--------|--------|-----------|
| Hash-Only Compliance | 100% | % of proofs using hashes only |
| GDPR Data Retention | 90 days max | No proof retained beyond lifecycle |
| Proof Lifecycle | < 1 year | Automatic expiration or renewal |
| Audit Log Integrity | 100% | All operations cryptographically signed |
| Regulatory Update Lag | < 30 days | Policy updates reflect new regulations |

## Integrator Compliance Responsibilities

### Your Obligations

When integrating SSID, external systems must:

1. **Consent Management**: Collect and log user consent for proof verification
   ```python
   if not user_has_consent_for("identity_verification"):
       raise ConsentRequiredError()
   ```

2. **Data Processing Agreements**: Execute DPA before production deployment
   - SSID template available in `23_compliance/legal/`
   - Specifies GDPR Article 28 obligations

3. **AML/CFT Integration**: Implement your own sanctions screening
   ```python
   sanctions_result = aml_provider.screen(user_hash)
   if sanctions_result.is_blocked:
       deny_access()
   ```

4. **Audit Logging**: Log all identity verification events in your system
   ```python
   audit_log.append({
       "timestamp": now(),
       "identity_hash": identity,
       "verifier_action": "access_granted",
       "jurisdiction": "EU"
   })
   ```

5. **Privacy Notice**: Update privacy policies to disclose SSID usage
   - Data shared: Cryptographic proofs only
   - Data retained: Per your retention policy
   - Third parties: SSID platform and KYC providers

### Proof of Compliance

Recommended documentation:

1. **Data Processing Inventory**
   - What identities you process
   - How long you retain proofs
   - Who has access

2. **Compliance Assessment**
   - Which SSID compliance level used
   - Which jurisdictions applicable
   - Risk analysis

3. **Incident Response Plan**
   - How you handle proof revocations
   - Breach notification procedures
   - Recovery time objectives

## Compliance Testing

### Self-Assessment

Run compliance tests on your integration:

```bash
cd 12_tooling/tests
pytest test_compliance_*.py -v

# Expected output:
# test_gdpr_hash_only PASSED
# test_eidas_signature_validation PASSED
# test_mica_fee_transparency PASSED
```

### External Audit

SSID undergoes:
- Annual security audit
- Quarterly bias audits (for AI components)
- Regulatory compliance reviews (GDPR, eIDAS)
- SOC 2 Type II assessment (planned Q3 2026)

Results published at: `23_compliance/evidence/audits/`

## Support & Resources

- **Compliance Questions**: Open issue on GitHub with `compliance` label
- **DPA Template**: `23_compliance/legal/data_processing_agreement.md`
- **DPIA**: `23_compliance/docs/dpia_assessment.md`
- **Audit Reports**: `23_compliance/evidence/audits/`

## Regulatory Intelligence

SSID tracks regulatory changes:

| Regulation | Last Update | Status |
|-----------|------------|--------|
| GDPR | 2026-01-15 | ✓ Implemented |
| eIDAS 2.0 | 2026-02-01 | ✓ Implemented |
| MiCA | 2024-12-01 | ✓ Implemented |
| NIS2 | TBD | ⧗ In Progress |
| DORA | TBD | ⧗ In Progress |
| EU AI Act | TBD | ⧗ In Progress |

## Disclaimers

1. **Not Legal Advice**: This document is technical guidance only. Consult legal counsel for your specific jurisdiction.

2. **Your Compliance Responsibility**: SSID Open-Core enables compliance, but deployment compliance is integrator's responsibility.

3. **Regulatory Changes**: Regulations evolve. Subscribe to `23_compliance/regulatory_intelligence/` for updates.

4. **Export Control**: SSID cryptographic components may be subject to export control. Verify applicability in your jurisdiction.

## Version & Status

| Item | Value |
|------|-------|
| Framework Version | 1.0.0-rc2 |
| Last Updated | 2026-04-13 |
| Compliance Level | Level 3 (eIDAS) |
| Status | Production Ready (Testnet) |
| Next Review | 2026-07-13 (Quarterly) |

---

For detailed regulatory framework specifications, see `23_compliance/frameworks/` directory.

For governance and DAO compliance rules, see `23_compliance/governance/` directory.

For security compliance, see `23_compliance/security/` directory.
