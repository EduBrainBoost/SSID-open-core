# Changelog

All notable changes to SSID-open-core are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- Phase 5: Public release roadmap execution
- Enhanced documentation and examples
- Community contribution framework

## [0.1.0] — 2026-04-13

**Initial Public Release**

This is the first public release of SSID-open-core as a certified governance-aligned open-core derivative of canonical SSID.

### Added

- ✅ **5 Exported Roots** — Full open-source public API
  - `03_core`: SSID runtime and core validators
  - `12_tooling`: CLI tools, deployment scripts, validators
  - `16_codex`: Architecture decisions, governance policies
  - `23_compliance`: Compliance policies and audit framework
  - `24_meta_orchestration`: Multi-agent coordination

- ✅ **Governance Framework**
  - ADR-0019: Export boundary realignment
  - ADR-0020: Test simulation classification
  - EXPORT_BOUNDARY.md: Authoritative 5-root policy
  - Validation gates with deterministic enforcement

- ✅ **Community Tools**
  - Public API documentation
  - Development setup guide
  - Contribution process (RFC-based)
  - Community support structure

- ✅ **Validation & Safety**
  - Deterministic validation gates (5 critical, 1 non-critical)
  - Private repo reference detection (0 violations)
  - Absolute path detection (0 violations)
  - Secret pattern detection (0 violations)
  - Denied root emptiness verification (19/19 confirmed)

- ✅ **Operational Procedures**
  - Quarterly governance reviews
  - Policy amendment process
  - Incident response procedures
  - Evidence logging and audit trail

### Changed

- Updated README.md for public release clarity
- Updated CONTRIBUTING.md for community contributions
- Enhanced validation scripts for comprehensive gate coverage
- CI/CD workflows optimized for exported roots only

### Fixed

- Phase 3: Resolved all 4 critical governance violations
  - Removed 42 code files from denied roots
  - Removed 145+ internal artifacts from exported roots
  - Ensured all 19 denied roots are empty scaffolds
  - Zero private repo references, zero absolute paths

- Phase 4: Test migration
  - Moved export tests from denied root (11_test_simulation) to exported root (12_tooling/tests/export/)
  - Updated CI workflows to reference new locations

### Security

- All secrets removed from exported roots
- No absolute local paths in public API
- No private repository references
- Complete evidence trail for all changes
- Backup available for rollback capability

### Documentation

- Complete governance audit report (437 lines)
- Phase 2-3 completion reports with detailed findings
- Decision package for external stakeholders
- Public API guide (in progress)
- Governance maintenance procedures

### Infrastructure

- 13 Phase 2-3 commits with full traceability
- Backup archive: backup_denied_roots_20260413.tar.gz (297 KB)
- CI/CD validation gates (5 critical + 1 warning)
- Evidence logging system

---

## Versioning Policy

- **v0.1.0** — Stable API, community-ready
- **v0.x.y** — Public API may evolve; export boundary is locked
- **v1.0.0** — Future major version when production-grade features added

## Support

For questions or issues, see:
- [SUPPORT.md](SUPPORT.md) — Support options and SLAs
- [SECURITY.md](SECURITY.md) — Security reporting
- [CONTRIBUTING.md](CONTRIBUTING.md) — How to contribute

## Release Schedule

- **v0.1.0** — April 13, 2026 (current)
- **v0.2.0** — Q2 2026 (planned)
- **v1.0.0** — Q3 2026 (projected)

Security patches may be released out-of-cycle as needed.

---

**Repository:** https://github.com/EduBrainBoost/SSID-open-core  
**License:** Apache 2.0  
**Status:** Stable, Community-Ready
