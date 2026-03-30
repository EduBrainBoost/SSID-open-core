# R021: Compliance Automation Status

**Last Updated:** 2026-03-28
**Roadmap Item:** R021
**Overall Status:** IN_PROGRESS

---

## Overview

R021 implements automated compliance monitoring for SSID across all regulatory
frameworks (MiCA, eIDAS, GDPR, FATF, AMLD6). The system reads framework YAML
definitions, checks evidence artefacts, generates findings, and produces
reports in Markdown and JSON format.

---

## Artefact Status

### Source Files

| File | Status | Path |
|---|---|---|
| automated_compliance_monitor.py | CREATED | `23_compliance/src/automated_compliance_monitor.py` |
| compliance_dashboard_data.py | CREATED | `23_compliance/src/compliance_dashboard_data.py` |
| compliance_report_generator.py | CREATED | `23_compliance/src/compliance_report_generator.py` |
| runtime_checker.py | PRE-EXISTING | `23_compliance/src/runtime_checker.py` |
| __init__.py | PRE-EXISTING | `23_compliance/src/__init__.py` |

### Configuration

| File | Status | Path |
|---|---|---|
| compliance_automation_config.yaml | CREATED | `23_compliance/config/compliance_automation_config.yaml` |

### Framework Data (Pre-Existing)

| Framework | Files | Path |
|---|---|---|
| MiCA | mica_controls.yaml, mica_mapping.yaml | `23_compliance/frameworks/mica/` |
| eIDAS | eidas_mapping.yaml, eidas_trust_services.yaml | `23_compliance/frameworks/eidas/` |
| GDPR | gdpr_controls.yaml, gdpr_mapping.yaml | `23_compliance/frameworks/gdpr/` |
| FATF | fatf_controls.yaml, fatf_mapping.yaml | `23_compliance/frameworks/fatf/` |
| AMLD6 | amld6_controls.yaml, amld6_mapping.yaml | `23_compliance/frameworks/amld6/` |
| ISO 27001 | Present | `23_compliance/frameworks/iso27001/` |
| SOC2 | Present | `23_compliance/frameworks/soc2/` |

---

## Module Architecture

```
AutomatedComplianceMonitor
    |
    +-- Loads framework YAML files from 23_compliance/frameworks/
    +-- Checks controls against evidence in 23_compliance/evidence/
    +-- Generates ComplianceFinding objects
    +-- Returns MonitoringResult
    |
ComplianceDashboardData
    |
    +-- Wraps AutomatedComplianceMonitor
    +-- Aggregates per-framework FrameworkStatus
    +-- Computes coverage percentages
    +-- Identifies gaps and overdue reviews
    +-- Returns CoverageReport
    |
ComplianceReportGenerator
    |
    +-- Wraps ComplianceDashboardData
    +-- generate_markdown_report() -> Markdown string
    +-- generate_json_report() -> JSON string
    +-- save_report() -> writes to 23_compliance/reports/
```

---

## Exported Interfaces

### automated_compliance_monitor.py

- `AutomatedComplianceMonitor` -- Main monitor class
- `ComplianceFinding` -- Single finding dataclass
- `MonitoringResult` -- Aggregate run result
- `Severity` -- Enum: critical, high, medium, low, info
- `FindingStatus` -- Enum: open, remediated, accepted_risk, false_positive
- `ControlStatus` -- Enum: implemented, partial, not_implemented, not_applicable

### compliance_dashboard_data.py

- `ComplianceDashboardData` -- Dashboard aggregator
- `FrameworkStatus` -- Per-framework summary
- `CoverageReport` -- Cross-framework coverage report

### compliance_report_generator.py

- `ComplianceReportGenerator` -- High-level report generator
- `generate_markdown_report()` -- Standalone Markdown generation
- `generate_json_report()` -- Standalone JSON generation

---

## Configuration Reference

File: `23_compliance/config/compliance_automation_config.yaml`

- **frameworks**: List of monitored frameworks with paths, intervals, priorities
- **alert_channels**: Log, webhook, email targets with severity thresholds
- **report_output_path**: `23_compliance/reports/`
- **evidence_requirements**: Per-framework max age, required evidence types, review cadence
- **monitoring_schedule**: 24h interval, 02:00 UTC start, run-on-startup

---

## Remaining Work

| Item | Priority | Notes |
|---|---|---|
| Unit tests | HIGH | Test each module against mock framework YAML |
| Integration test | HIGH | End-to-end run against real evidence directory |
| __init__.py update | MEDIUM | Add new modules to package exports |
| Scheduled runner | MEDIUM | Cron/systemd integration for periodic execution |
| Alert channel implementation | LOW | Webhook and email dispatch (currently log-only) |
| Evidence freshness tuning | LOW | Per-framework age thresholds from config |

---

## Dependencies

- Python 3.10+
- PyYAML (for framework YAML parsing)
- No external API dependencies (all local file-based)
- Framework YAML files must follow existing schema in `23_compliance/frameworks/`
