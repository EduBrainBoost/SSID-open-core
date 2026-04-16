# SSID-open-core Repo Gate Map

## Overview
This document defines the 6 mandatory gates for SSID-open-core repository code, design, and deployment decisions. All code changes must pass these gates sequentially before merging to main.

**Repository:** SSID-open-core  
**Total Gates:** 6  
**Gate Sequence:** Crypto → Regulatory → Privacy → Evidence → Boundary → Closed Pilot Gate

---

## Gate 1: Crypto (EX-C)

**Owner:** External Crypto Mandate (EX-C)

### Minimum Pass Evidence
- [ ] Smart contract audit (full or delta audit)
- [ ] Zero-knowledge proof validation
- [ ] Post-quantum crypto compliance (Kyber/Dilithium)
- [ ] Key management audit (non-custodial verification)
- [ ] Cryptographic primitives pre-approved
- [ ] Hash function validation (SHA3-256 or Keccak)

### Hard Fail Triggers
- Private keys in code or config
- Non-approved cryptographic functions
- Smart contract changes without RFC
- Post-quantum standards violated
- Custodial key storage detected
- Weak cryptographic primitives used

---

## Gate 2: Regulatory (EX-L)

**Owner:** External Legal/Regulatory Mandate (EX-L)

### Minimum Pass Evidence
- [ ] EU AI Act compliance (Articles 22-25)
- [ ] No system secrets in code
- [ ] No KYC/AML credentials exposed
- [ ] Audit logging enabled and tested
- [ ] License compliance verified
- [ ] Smart contract legality statement

### Hard Fail Triggers
- EU AI Act non-compliance
- System secrets exposed
- Audit logging disabled
- License terms violated
- Smart contract legal risk unmitigated
- Regulatory frameworks ignored

---

## Gate 3: Privacy (EX-P)

**Owner:** External Privacy Mandate (EX-P)

### Minimum Pass Evidence
- [ ] No PII in smart contracts or storage
- [ ] SHA3-256 hashing for user identifiers
- [ ] Federated Learning standards met
- [ ] Data retention policy documented
- [ ] GDPR compliance statement
- [ ] Privacy-preserving design validated

### Hard Fail Triggers
- PII stored in contracts
- Non-hashed user identifiers
- Federated Learning standards violated
- Privacy policy missing
- GDPR non-compliance
- Privacy impact assessment missing

---

## Gate 4: Evidence (S5)

**Owner:** Seat-5 (Evidence & Audit)

### Minimum Pass Evidence
- [ ] Evidence log completed (all operations)
- [ ] SHA256 hashes (before & after) recorded
- [ ] SAFE-FIX confirmation for overwrites
- [ ] All commits signed and attributed
- [ ] Root-24 scope compliance verified
- [ ] Session isolation maintained
- [ ] Lock file integrity confirmed

### Hard Fail Triggers
- Evidence log incomplete
- SHA256 hashes missing
- SAFE-FIX confirmation missing
- Unsigned commits detected
- Out-of-scope modifications
- Session isolation violated
- Lock file corruption

---

## Gate 5: Boundary (S1 + S5)

**Owner:** Seat-1 (Meta-Orchestrator) + Seat-5 (Evidence & Audit)

### Minimum Pass Evidence
- [ ] Open-source export scope verified (3,001+ files)
- [ ] All proprietary code removed
- [ ] Copyright/license headers correct
- [ ] Code quality metrics baseline met
- [ ] Performance benchmarks established
- [ ] Security scanners passed (SAST)
- [ ] Dependency audits passed
- [ ] GitHub release preparation verified

### Hard Fail Triggers
- Proprietary code remains in export
- Incorrect copyright headers
- License violations detected
- Code quality below baseline
- Security scan failures (CRITICAL)
- Unaudited dependencies
- Export scope compromised
- Release integrity broken

---

## Gate 6: Closed Pilot Gate (Combined Validation)

**Owner:** Seat-1 (Meta-Orchestrator) with all 5 previous gate owners

### Minimum Pass Evidence
- [ ] ALL 5 previous gates PASS
- [ ] Cross-repo consistency verified (SSID ↔ open-core)
- [ ] Integration testing complete (106+ tests)
- [ ] Pilot exit criteria met (30+ acceptance checks)
- [ ] Production readiness attestation
- [ ] Go-live sequence stage-gate met

### Hard Fail Triggers
- Any previous gate FAILS
- Cross-repo inconsistencies detected
- Integration tests fail
- Pilot exit criteria not met
- Production readiness blocked
- Go-live dependencies missing

---

## Gate Sequence Logic

```
Crypto (EX-C) ✓
    ↓ [PASS]
Regulatory (EX-L) ✓
    ↓ [PASS]
Privacy (EX-P) ✓
    ↓ [PASS]
Evidence (S5) ✓
    ↓ [PASS]
Boundary (S1+S5) ✓
    ↓ [PASS]
Closed Pilot Gate ✓
    ↓ [PASS]
→ MERGEABLE TO MAIN + READY FOR RELEASE
```

**Sequential Gates Rule:** Each gate must PASS before proceeding to the next. No gate skipping. Gate 6 requires ALL previous gates PASS.

---

## Open-Core Specific Rules

### Export Requirements
- **Total Files:** 3,001+ (phases 1-7 complete)
- **Proprietary Removal:** Zero proprietary code in export
- **Copyright Headers:** All files correctly attributed
- **License:** Apache 2.0 or GPL-compatible only

### Smart Contract Requirements
- Solidity version: 0.8.x or later
- Compiled bytecode verified
- Audit report present (delta audit acceptable post-initial)
- Gas optimization standards met
- Test coverage: > 85%

### Code Quality
- Linting: 0 critical, 0 high violations
- SAST scanning: 0 critical findings
- Dependency audit: 0 unpatched critical vulnerabilities
- Code coverage: > 80%

### Release Artifacts
- GitHub release with:
  - Full changelog
  - Smart contract audit (if applicable)
  - Breaking changes documented
  - Migration guide (if applicable)
  - Docker images available (if applicable)

---

## Integration with Pilot Control Plane

This gate map is integrated with:
- **Pilot Exit Criteria:** All 30+ acceptance checks mapped to 6 gates
- **Go-Live Sequence:** 25-step framework with crypto/regulatory/privacy critical gates
- **Closed Pilot Target:** 6/6 PASS = CLOSED_PILOT_APPROVED

---

## Cross-Repo Consistency Requirements

### With SSID Core
- Smart contract interfaces must match
- Cryptographic standards aligned
- Privacy policies consistent
- Evidence logging compatible

### With SSID-EMS
- API contracts validated
- Integration tests passing
- Performance baselines aligned
- Dependency versions compatible

### With SSID-orchestrator
- Swarm closeout rules enforced
- Evidence chain compatible
- Lock mechanism integrated
- Session isolation verified

---

## Enforcement

- **CI Integration:** All 6 gates enforced sequentially
- **Evidence Tracking:** Complete audit trail for all operations
- **Abort Logic:** ANY gate FAIL blocks merge immediately
- **Status Transparency:** Real-time gate status in PR checks
- **Truth Gate:** orchestrator_truth_gate.py validates cross-repo consistency
- **Release Gating:** Gate 6 PASS required for release promotion

---

## Testing & Validation

- **Unit Tests:** 500+ covering all modules
- **Integration Tests:** 106+ multi-contract workflows
- **Security Tests:** SAST + dependency audits
- **Load Tests:** Performance baselines established
- **Release Tests:** Export integrity verified
- **Pilot Tests:** All 30+ exit criteria validated

Last Updated: 2026-04-16
