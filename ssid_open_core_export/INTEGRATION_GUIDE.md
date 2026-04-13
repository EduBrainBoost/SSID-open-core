# SSID Open-Core Integration Guide

For external developers integrating SSID Open-Core modules into your systems.

## Quick Start

### Prerequisites
- Python 3.10+
- pip or Poetry for dependency management
- Basic familiarity with identity systems and cryptographic proofs

### Installation

1. **Extract the Export**
```bash
unzip ssid_open_core_export.zip
cd ssid_open_core_export
```

2. **Verify Integrity**
```bash
sha256sum -c export.sha256.txt
```

### SDK Usage (Python)

#### Identity Verification Module
```python
from ssid_open_core.identity import IdentityVerifier

# Initialize verifier
verifier = IdentityVerifier(
    rpc_endpoint="https://your-rpc.example.com",
    registry_address="0x..."
)

# Verify identity proof
result = verifier.verify_proof(
    identity_hash="0x...",
    proof_signature="0x...",
    timestamp=1234567890
)

if result.valid:
    print(f"Identity verified: {result.identity_hash}")
else:
    print(f"Verification failed: {result.error}")
```

#### Compliance Checker
```python
from ssid_open_core.compliance import ComplianceValidator

validator = ComplianceValidator(jurisdiction="EU")

# Check regulatory compliance
compliance_status = validator.check_compliance(
    user_data_handling="hash_only",
    retention_period_days=90,
    pii_storage="none"
)

print(f"Compliant: {compliance_status.compliant}")
print(f"Gaps: {compliance_status.violations}")
```

## Core Modules

### 03_core: Smart Contracts & Dispatcher
- **admin_api**: REST API for governance and identity management
- **validators**: Proof verification and validation rules
- **security**: Non-custodial architecture enforcement
- **policy**: Regulatory policy integration

**Relevant Classes**:
- `ProofValidator`: Validates cryptographic proofs
- `ComplianceEnforcer`: Enforces non-custodial rules
- `DispatcherEngine`: Executes identity workflows

### 12_tooling: CLI & SDKs
- **agent**: Multi-agent orchestration framework
- **cli**: Command-line interface (ssidctl)
- **testnet_mvp**: Testnet deployment and testing tools
- **sbom**: Software Bill of Materials generation

**Command Examples**:
```bash
ssidctl identity create --name "user@example.com"
ssidctl proof generate --identity-id "..." --provider "didit"
ssidctl validate --compliance-level "eidas"
```

### 16_codex: Knowledge Base
- **decisions**: Architecture Decision Records (ADRs)
- **governance**: Governance policies and voting
- **opencore_export_policy.yaml**: Export boundary definitions
- **phases**: Completion reports and roadmaps

**Key Documents**:
- ADR-0001: Non-custodial architecture principles
- ADR-0002: Repository separation and export boundaries
- governance/DAO_CHARTER.md: DAO governance rules

### 23_compliance: Regulatory Framework
- **mappings**: Regulatory requirement mappings
- **governance**: Community guidelines and approvals
- **runtime_checker.py**: Runtime compliance validation

**Compliance Levels**:
- `level_1_basic`: Minimal compliance (general terms)
- `level_2_gdpr`: GDPR compliance
- `level_3_eidas`: eIDAS digital signature compliance
- `level_4_mica`: MiCA crypto asset compliance

### 24_meta_orchestration: Orchestration Runtime
- **contracts**: Proof registry and smart contract specs
- **dispatcher**: Workflow execution engine
- **registry**: Identity and policy registry
- **tasks**: Task execution and recovery procedures

## API Endpoints

### Admin API (03_core)

**Base URL**: `http://localhost:8000`

#### Identities
```
POST   /api/v1/identities          - Create new identity
GET    /api/v1/identities/{id}     - Retrieve identity
PUT    /api/v1/identities/{id}     - Update identity
DELETE /api/v1/identities/{id}     - Delete identity (governance)
```

#### Proofs
```
POST   /api/v1/proofs              - Submit proof
GET    /api/v1/proofs/{id}         - Retrieve proof
POST   /api/v1/proofs/{id}/verify  - Verify proof
```

#### Compliance
```
GET    /api/v1/compliance/status   - Compliance status
POST   /api/v1/compliance/check    - Check compliance
GET    /api/v1/compliance/report   - Generate compliance report
```

#### Governance
```
GET    /api/v1/governance/votes    - List active votes
POST   /api/v1/governance/vote     - Cast vote
GET    /api/v1/governance/policies - List policies
```

## Configuration

### Environment Variables
```bash
# API Configuration
SSID_API_HOST=0.0.0.0
SSID_API_PORT=8000
SSID_API_DEBUG=false

# Blockchain Configuration
SSID_RPC_ENDPOINT=https://rpc.example.com
SSID_CONTRACT_REGISTRY=0x...
SSID_CHAIN_ID=1  # Ethereum mainnet

# KYC Provider Configuration
SSID_KYC_PROVIDER=didit  # or: sign-me, namirial, infocert, quadrata
SSID_KYC_API_KEY=your_api_key
SSID_KYC_API_SECRET=your_api_secret

# Compliance Configuration
SSID_COMPLIANCE_LEVEL=eidas
SSID_JURISDICTION=EU
SSID_DATA_RETENTION_DAYS=90

# Logging
SSID_LOG_LEVEL=INFO
SSID_LOG_FORMAT=json
```

### Configuration File (config.yaml)
```yaml
api:
  host: 0.0.0.0
  port: 8000
  debug: false

blockchain:
  rpc_endpoint: https://rpc.example.com
  chain_id: 1
  contracts:
    registry: "0x..."
    dispatcher: "0x..."

kyc_providers:
  - name: didit
    api_key: ${SSID_KYC_API_KEY}
    api_secret: ${SSID_KYC_API_SECRET}

compliance:
  level: eidas
  jurisdiction: EU
  retention_days: 90
```

## Common Integration Patterns

### Pattern 1: Verify Identity Proof
```python
from ssid_open_core.identity import verify_proof

# Verify proof from external source
is_valid = verify_proof(
    proof_data={
        "identity_hash": "0x...",
        "signature": "0x...",
        "timestamp": 1234567890,
        "provider": "didit"
    }
)

if is_valid:
    # Grant access or create account
    create_user_session()
else:
    # Reject or request new proof
    request_new_proof()
```

### Pattern 2: Check Regulatory Compliance
```python
from ssid_open_core.compliance import validate_processing

# Validate data processing against GDPR
compliance = validate_processing(
    user_id="user_hash",
    data_types=["identity", "email"],
    purposes=["authentication", "fraud_prevention"],
    jurisdiction="EU"
)

if not compliance.compliant:
    log_violation(compliance.gaps)
    request_consent_update()
```

### Pattern 3: Execute Governance Vote
```python
from ssid_open_core.governance import submit_vote

# Participate in DAO governance
vote_receipt = submit_vote(
    proposal_id="prop_123",
    vote="for",
    voting_power=100_000_000  # tokens
)

monitor_vote_outcome(vote_receipt)
```

## Testing

### Unit Tests
```bash
cd 12_tooling/tests
pytest test_*.py -v
```

### Integration Tests
```bash
# Start testnet mock services
python testnet_mvp/01_hash_only_proof_registry/scripts/deploy_testnet.py

# Run integration tests
pytest integration_tests/ -v
```

### End-to-End Tests
```bash
# Full flow test: Create identity → Generate proof → Verify compliance
pytest e2e_tests/test_full_workflow.py -v
```

## Deployment

### Docker
```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY ssid_open_core_export/ .

RUN pip install -r 12_tooling/requirements.txt

CMD ["python", "12_tooling/cli/main.py", "api", "--host", "0.0.0.0", "--port", "8000"]
```

### Kubernetes
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ssid-open-core
spec:
  replicas: 3
  selector:
    matchLabels:
      app: ssid-open-core
  template:
    metadata:
      labels:
        app: ssid-open-core
    spec:
      containers:
      - name: api
        image: ssid-open-core:v1.0.0-rc2
        ports:
        - containerPort: 8000
        env:
        - name: SSID_RPC_ENDPOINT
          valueFrom:
            configMapKeyRef:
              name: ssid-config
              key: rpc_endpoint
```

## Support & Resources

- **Documentation**: See ARCHITECTURE.md and COMPLIANCE.md in this directory
- **Code Examples**: 12_tooling/examples/
- **Test Cases**: 12_tooling/tests/
- **Issues & Questions**: https://github.com/EduBrainBoost/SSID-open-core/issues

## License

SSID Open-Core modules are distributed under community-compatible open-source licenses. See LICENSE files in each module directory.

