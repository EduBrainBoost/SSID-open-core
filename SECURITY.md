# Security Policy

## Reporting Security Issues

**Please do NOT file security issues on the public GitHub issue tracker.**

If you discover a security vulnerability in SSID-open-core, please report it to:

📧 **[security@example.com](mailto:security@example.com)**

Include:
- Description of the vulnerability
- Affected component (which root/script/version)
- Steps to reproduce (if safe to disclose)
- Impact assessment (e.g., authentication bypass, data exposure)
- Any potential fixes you've identified

## Response Process

We aim to:
1. ✅ Acknowledge receipt within **24 hours**
2. ✅ Confirm the vulnerability within **48 hours**
3. ✅ Develop a fix in private
4. ✅ Release a security patch
5. ✅ Publish a security advisory (with coordination)

## Security Advisory Process

1. **Reporting** — Private report to security@example.com
2. **Triage** — Confirm severity and affected versions
3. **Fix Development** — Create patch in private branch
4. **Testing** — Validate the fix thoroughly
5. **Coordination** — Work with reporters on disclosure timeline
6. **Release** — Publish patch and advisory simultaneously
7. **Announcement** — Public notification to users

## Supported Versions

Security updates are provided for:
- **Current Release** (v0.1.0) — Full support
- **Next Release** (v0.2.0) — Upon release
- **Older Versions** — No longer supported (upgrade recommended)

## Security Best Practices

### For Users
- Keep SSID-open-core updated to the latest version
- Review security advisories regularly
- Enable secret scanning and dependency checks
- Report suspicious behavior immediately

### For Contributors
- Never commit secrets, API keys, or credentials
- Use environment variables for sensitive data
- Review changes for security implications
- Follow secure coding practices

## Validation Gates

SSID-open-core includes deterministic security validation:

✅ **Private repo references** — 0 violations  
✅ **Absolute local paths** — 0 violations  
✅ **Secret patterns** — 0 violations  
✅ **Denied root code** — All 19 are empty  

All gates must PASS before merge.

---

**Questions?** Contact [security@example.com](mailto:security@example.com)
