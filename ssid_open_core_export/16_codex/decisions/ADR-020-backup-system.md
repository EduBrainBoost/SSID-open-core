# ADR-020: Professional Backup System Integration

## Status

Accepted -- 2026-04-04

## Context

SSID requires an automated, auditable backup system to protect all five active
repositories (SSID, SSID-EMS, SSID-docs, SSID-open-core, SSID-orchestrator).

Prior to this ADR, the backup landscape consisted of:
- A prototype `backup_runner.py` in `15_infra/backup/` with file-level snapshots
- An async `backup_automation_daemon.py` in `12_tooling/scripts/` (mock execution)
- Configuration files (`backup_automation_config.yaml`, `backup_policy.yaml`)
- Restore test scheduling in `11_test_simulation/config/`
- Recovery SLA contract in `17_observability/config/`

The gap analysis (BACKUP_RECOVERY_ASSESSMENT.md) identified a 48% recovery readiness
score, with critical gaps in:
- Automated backup execution (git bundles)
- Encryption at rest
- Retention automation
- Evidence hash-chain (WORM-compatible)
- Prometheus metrics and AlertManager alerts
- CI/CD integration

## Decision

Implement a multi-tier backup system distributed across the canonical Root-24
structure:

| Root | Component | Purpose |
|------|-----------|---------|
| 15_infra/backup/ | backup_scheduler.py | Cron-based job orchestration |
| 15_infra/backup/ | backup_writer.py | Git-bundle + compression + encryption |
| 15_infra/backup/ | retention_manager.py | Retention policy enforcement |
| 15_infra/backup/ | backup_config.yaml | Central configuration |
| 02_audit_logging/backup/ | backup_evidence.py | SHA256 hash-chain (WORM) |
| 02_audit_logging/backup/ | backup_ledger_schema.json | Evidence entry schema |
| 17_observability/backup/ | backup_metrics.py | Prometheus exporter |
| 17_observability/backup/ | backup_alerts.yaml | AlertManager rules |
| 11_test_simulation/backup/ | Integration + restore tests | E2E verification |
| 04_deployment/backup/ | K8s CronJob + CI workflow | Operational deployment |
| 16_codex/decisions/ | This ADR | Architecture decision record |

### Design Principles

1. **SAFE-FIX compliant**: Every write operation produces SHA256 before/after evidence
2. **Non-custodial**: No PII in backup filenames or metadata
3. **ROOT-24-LOCK**: No new root directories; all components in existing roots
4. **Vault-sourced encryption**: AES-256 via Fernet, key from HashiCorp Vault
5. **PQC migration path**: AES-256 today, Kyber-compatible when available
6. **Atomic writes**: tmp-to-final rename pattern prevents partial artifacts
7. **WORM evidence chain**: Append-only ledger with cumulative hash chain

### Backup Types

- **Full**: Complete git-bundle of all refs (weekly)
- **Incremental**: Git-bundle since last backup tag (daily)
- **Snapshot**: Lightweight hash-manifest of working tree (every 6h)

### Retention Policy

- Daily: 7 retained
- Weekly: 4 retained
- Monthly: 12 retained
- Maximum total: 50 GB
- Minimum free space: 10 GB

## Consequences

### Positive
- Automated, evidence-based backup with full audit trail
- Prometheus-monitored with AlertManager alerting
- PQC-ready encryption (AES-256 with Kyber migration path)
- Recovery readiness projected to improve from 48% to 95%+
- WORM-compatible evidence chain detects tampering

### Negative
- Additional disk space consumption (~50 GB maximum)
- Dependency on HashiCorp Vault for encryption key management
- Requires `cryptography` package for Fernet encryption (optional graceful degradation)

### Risk Mitigated
- Data loss from accidental deletion or corruption
- Undetected tampering of backup artifacts
- Missed backups without alerting
- Restore failures without prior testing

## References

- BACKUP_INVENTORY.md: Existing backup artifact inventory
- BACKUP_SOT_REQUIREMENTS.md: SoT conformance requirements
- BACKUP_RECOVERY_ASSESSMENT.md: Gap analysis and readiness score
- BACKUP_MASTERPLAN_v1.0.md: Implementation plan
- 17_observability/config/recovery_sla_contract.yaml: RTO/RPO SLAs
- 11_test_simulation/config/restore_test_schedule.yaml: Restore test scheduling
