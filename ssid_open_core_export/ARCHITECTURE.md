# SSID Open-Core Architecture

## System Overview

SSID is a self-sovereign identity system built on eight foundational pillars that work together to create a verifiable, non-custodial identity platform. This architecture guide documents the design principles, component relationships, and integration points for external developers.

## Eight Pillars Architecture

The SSID system is structured around eight core pillars, each providing essential security, compliance, and operational guarantees:

### Pillar 1: Truth (Source of Truth)

**Principle**: Single canonical source for entire system definition.

- **SOT Validator** (`03_core/validators/sot/`): Validates all configurations against single source of truth
- **sot_master_merged.json**: Canonical merged reference file
- **Guarantee**: Zero deviation from SOT is tolerated

All system configuration, governance rules, and compliance policies derive from a single authoritative source, preventing configuration drift and conflicting definitions.

### Pillar 2: Structure (ROOT-24-LOCK)

**Principle**: System structure is frozen and immutable.

- **ROOT-24-LOCK**: 24 root directories are canonical; no creation, renaming, or deletion permitted
- **Structure Guard** (`12_tooling/scripts/structure_guard.sh`): Automated structural integrity verification
- **Guarantee**: No agent or process can modify root structure

This immutable structure ensures predictable repository organization and prevents accidental architectural changes that could compromise system integrity.

### Pillar 3: Control (Dispatcher + SAFE-FIX)

**Principle**: Every system action is controlled, logged, and auditable.

- **Dispatcher v4.1** (`24_meta_orchestration/dispatcher/`): Non-interactive mode with SHA256 logging
- **SAFE-FIX Enforcement**: Additive-only writes, evidence logging mandatory, no blind overwrites
- **Guarantee**: No uncontrolled system modifications possible

All state changes are explicitly tracked with before/after hashes, enabling full auditability and recovery.

### Pillar 4: Cryptography (SHA256 + Post-Quantum)

**Principle**: All proofs and identities are cryptographically secured.

- **SHA256 Evidence** (`21_post_quantum_crypto/`): Every file change documented with before/after hashes
- **PQC Standards**: Kyber and Dilithium for post-quantum resistance
- **Guarantee**: Quantum-computer-resistant security for all cryptographic operations

### Pillar 5: CI/CD + Registry

**Principle**: Automated quality assurance and agent lifecycle management.

- **23 GitHub Actions Workflows**: Automated build, test, and deployment pipelines
- **Agent Registry**: Centralized management of system agents and permissions
- **Guarantee**: No code reaches main without automated verification

### Pillar 6: Audit + Evidence (WORM)

**Principle**: Every system action creates immutable audit evidence.

- **WORM Evidence** (`02_audit_logging/`): Write Once, Read Many -- 19,882+ audit entries
- **JSON Evidence Logs**: Structured entries with timestamp, agent ID, SHA256 hashes
- **Guarantee**: Complete auditability of all system actions

### Pillar 7: Governance + Compliance

**Principle**: Compliance and governance are machine-readable, not just documentation.

- **13 OPA Policies** (`23_compliance/policies/`): Open Policy Agent rules
- **Compliance Framework**: GDPR, ePrivacy, EU AI Act conformance
- **Guarantee**: Policy violations automatically detected and blocked

### Pillar 8: Self-Adaptation (TSAR Engine)

**Principle**: System monitors, analyzes, and optimizes itself.

- **TSAR Engine** (`24_meta_orchestration/tsar/`): Threat-Sensitive Adaptive Response
- **Self-Healing**: Automatic correction of detected deviations
- **Guarantee**: System remains functional and integral even under attack

## Component Architecture

### Layer 1: Core Smart Contracts & Dispatcher (`03_core`)

**Responsibility**: Identity proof verification, dispatcher orchestration, access control.

**Key Components**:
- **Admin API** (`admin_api/`): REST endpoints for identity, proof, compliance, governance management
- **Proof Validators** (`validators/`): Cryptographic proof verification rules
- **Dispatcher Engine**: Orchestrates identity workflows across system
- **Security Module**: Non-custodial architecture enforcement
- **Policy Integration**: Regulatory policy hooks

**API Endpoints**:
- `POST /api/v1/identities` — Create identity
- `POST /api/v1/proofs` — Submit proof
- `POST /api/v1/proofs/{id}/verify` — Verify proof signature
- `GET /api/v1/compliance/status` — Compliance status
- `POST /api/v1/governance/vote` — Cast governance vote

### Layer 2: CLI Tools & SDKs (`12_tooling`)

**Responsibility**: External integration, testing, automation.

**Key Components**:
- **ssidctl** (`cli/`): Command-line interface for all operations
- **Python SDKs** (`api/`): IdentityVerifier, ComplianceValidator classes
- **Multi-Agent Framework** (`agent/`): Agent orchestration for complex workflows
- **Testnet MVP** (`testnet_mvp/`): Local testnet for development
- **SBOM Generation** (`sbom/`): Software Bill of Materials creation

**Common Operations**:
```bash
ssidctl identity create --name "user@example.com"
ssidctl proof generate --identity-id "..." --provider "didit"
ssidctl validate --compliance-level "eidas"
```

### Layer 3: Knowledge Base & Governance (`16_codex`)

**Responsibility**: System documentation, policies, architecture decisions.

**Key Components**:
- **Architecture Decisions** (`decisions/`): ADRs (Architecture Decision Records)
- **Governance Policies** (`governance/`): DAO charter, voting rules
- **Export Boundaries** (`opencore_export_policy.yaml`): Public/private module definitions
- **Phase Completion Reports** (`phases/`): System evolution documentation

### Layer 4: Compliance & Evidence (`23_compliance`)

**Responsibility**: Regulatory framework, compliance validation, audit evidence.

**Key Components**:
- **Compliance Mappings** (`mappings/`): GDPR, eIDAS, MiCA requirement mappings
- **Governance Framework** (`governance/`): Community guidelines and approvals
- **Runtime Checker** (`runtime_checker.py`): Real-time compliance validation
- **Audit Evidence** (`evidence/`): Security audit reports and findings

**Compliance Levels**:
- **Level 1 (Basic)**: Minimal compliance (general terms)
- **Level 2 (GDPR)**: EU data protection compliance
- **Level 3 (eIDAS)**: Digital signature and eID regulations
- **Level 4 (MiCA)**: Crypto asset regulation compliance

### Layer 5: Orchestration Runtime (`24_meta_orchestration`)

**Responsibility**: Workflow execution, registry management, multi-agent coordination.

**Key Components**:
- **Proof Registry** (`contracts/`): Smart contract specifications
- **Dispatcher** (`dispatcher/`): Workflow engine
- **Identity Registry** (`registry/`): Identity and policy registry
- **Task Executor** (`tasks/`): Task execution and recovery

## Data Flow Architecture

```
Identity Proof Submission
    ↓
[Proof Validator] (03_core)
    ↓
[Hash Computation] (SHA256)
    ↓
[Registry Lookup] (24_meta_orchestration)
    ↓
[Compliance Check] (23_compliance)
    ↓
[Proof Status Update] (03_core API)
    ↓
[Evidence Log] (02_audit_logging)
```

## Non-Custodial Architecture

SSID maintains strict non-custodial principles throughout this export:

- **Hash-Only Proofs**: No on-chain personally identifiable information (PII) storage
- **Zero Intermediation**: Direct relationships between users and identity providers
- **Transparent Fees**: 3% system, 1% developer, 2% pool
- **Smart Contracts**: Autonomous execution without manual intervention
- **Governance**: DAO-driven upgrades and policy changes

## Integration Points

External developers can integrate SSID Open-Core using:

1. **REST API** (`03_core/admin_api/`)
   - Identity verification endpoints
   - Proof submission and verification
   - Compliance checking
   - Governance voting

2. **Python SDKs** (`12_tooling/api/`)
   - IdentityVerifier class for proof validation
   - ComplianceValidator for regulatory checks
   - Governance interfaces for voting

3. **Command-Line Tools** (`12_tooling/cli/`)
   - ssidctl for local identity and proof management
   - Deployment automation
   - Testing and validation

4. **Smart Contracts** (`03_core/contracts/`)
   - On-chain proof registry
   - Governance smart contracts
   - Custom deployment rules

See `INTEGRATION_GUIDE.md` for detailed integration examples.

## Technology Stack

**Core Components**:
- Smart Contracts: Solidity (EVM-compatible)
- API Layer: Python FastAPI
- CLI: Python Click framework
- Storage: IPFS (distributed), PostgreSQL (structured)
- Blockchain: Ethereum-compatible networks (testnet MVP, mainnet ready)

**Security**:
- Cryptography: SHA256, Kyber (post-quantum), Dilithium (post-quantum)
- Authentication: JWT, DID Session Tokens, mTLS
- Secret Management: HashiCorp Vault integration

**Operations**:
- Containerization: Docker
- Orchestration: Kubernetes
- CI/CD: GitHub Actions (23 workflows)
- Monitoring: Prometheus, Jaeger distributed tracing

## Deployment Architecture

### Testnet MVP (Current)

- API Server: Python FastAPI on single node
- Smart Contracts: Deployed to Ethereum testnet
- Registry: In-memory with persistent backup
- Compliance: Local OPA policy engine

### Mainnet Ready (Future)

- API Server: Kubernetes cluster (3+ replicas)
- Smart Contracts: Mainnet deployment with governance controls
- Registry: Distributed database with replication
- Compliance: Multi-jurisdictional policy enforcement

## Governance & Evolution

Changes to core SSID architecture require:

1. **Architecture Decision Record (ADR)**: Document rationale and alternatives
2. **RFC Process**: Request For Comments from community
3. **Compliance Review**: Ensure regulatory alignment
4. **Security Audit**: Independent security assessment
5. **Governance Vote**: DAO approval (if applicable)

See `16_codex/decisions/` for all prior architectural decisions.

## Support & Resources

- **API Documentation**: See INTEGRATION_GUIDE.md
- **Compliance Details**: See COMPLIANCE.md
- **Architecture Decisions**: See 16_codex/decisions/
- **Code Examples**: See 12_tooling/examples/
- **Test Cases**: See 12_tooling/tests/

## License

SSID Open-Core modules are distributed under community-compatible open-source licenses. See LICENSE file in each module directory for specific licensing terms.

---

**Version**: 1.0.0-rc2
**Last Updated**: 2026-04-13
**Status**: Canonical
