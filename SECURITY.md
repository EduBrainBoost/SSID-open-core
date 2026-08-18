# Security Policy

## Supported Versions

Only the latest release of SSID-open-core receives security updates.

| Version | Supported |
|---------|-----------|
| 1.x     | ✅        |
| < 1.0   | ❌        |

## Reporting a Vulnerability

We take security seriously. If you discover a security vulnerability:

1. **Do NOT** open a public GitHub issue
2. Submit via GitHub Security Advisory (private report)
3. Include: description, reproduction steps, severity assessment
4. Allow 72 hours for initial response before public disclosure

## What This Repository Contains

SSID-open-core is a **public-safe mirror**. It intentionally contains:
- Public API schemas and interfaces
- Reference implementations with mock backends
- Synthetic test data
- Public documentation and examples

It does **NOT** contain:
- Production secrets or credentials
- Private SSID source code
- Real customer or user data
- Internal infrastructure configurations
- Private agent runtime code

## Security Scanning

Every commit is scanned for:
- 🔑 **Secrets**: API keys, tokens, certificates, passwords
- 📧 **PII**: Email addresses, phone numbers, IDs
- 📄 **License violations**: Unknown or incompatible licenses
- 🔒 **Private leakage**: SSID internal paths, system names, credentials
- 📦 **SBOM**: Software bill of materials for dependency tracking

## Scope Distinction

| Concern | Public OpenCore | Private SSID |
|---------|----------------|--------------|
| Source code | Reference/examples only | Full implementation |
| Secrets | None | Encrypted storage |
| PII | Synthetic data only | Production data |
| Endpoints | Placeholders/mocks | Production URLs |
| Control plane | None | Full access |

## Responsible Disclosure

- Vulnerabilities in public-facing content are disclosed within 90 days
- Third-party dependencies are monitored via automated scanning
- Critical fixes are backported to the latest supported version

## Audit Trail

All security scanning results are recorded in [23_compliance/evidence/](23_compliance/evidence/).
