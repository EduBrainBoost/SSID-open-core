# Support & Community

Need help with SSID-open-core? Here's how to get support.

## Getting Help

### Documentation
- **Quick Start:** [README.md](README.md)
- **Public API Guide:** [16_codex/PUBLIC_API_GUIDE.md](16_codex/PUBLIC_API_GUIDE.md)
- **Governance Policy:** [16_codex/EXPORT_BOUNDARY.md](16_codex/EXPORT_BOUNDARY.md)
- **Architecture:** [16_codex/decisions/](16_codex/decisions/)

### Community

#### GitHub Discussions
- 💬 **Ask questions** about usage and integration
- 🤔 **Share ideas** for improvements
- 📚 **Learn from others** — search prior discussions

[Go to GitHub Discussions →](https://github.com/EduBrainBoost/SSID-open-core/discussions)

#### GitHub Issues
- 🐛 **Report bugs** with reproduction steps
- 💡 **Request features** with use cases
- 📌 **See known issues** and workarounds

[Go to GitHub Issues →](https://github.com/EduBrainBoost/SSID-open-core/issues)

#### Email Support
- **Questions:** [community@example.com](mailto:community@example.com)
- **Security issues:** [security@example.com](mailto:security@example.com) (private, no GitHub issues)

## Issue Response SLA

We aim to respond within:

| Severity | Response Time | Resolution Target |
|----------|---------------|-------------------|
| 🔴 Critical | 24 hours | 3 business days |
| 🟠 High | 3 business days | 1 week |
| 🟡 Medium | 1 week | 2 weeks |
| 🟢 Low | Best effort | Monthly |

**Critical** = Security vulnerability or blocking issue  
**High** = Major functionality broken  
**Medium** = Feature incomplete or workaround exists  
**Low** = Minor issue or documentation gap

## Reporting Issues

### Before Reporting
1. Check [existing issues](https://github.com/EduBrainBoost/SSID-open-core/issues)
2. Review [documentation](16_codex/)
3. Search [discussions](https://github.com/EduBrainBoost/SSID-open-core/discussions)

### How to Report

**Include:**
- Clear title and description
- Steps to reproduce (if bug)
- Expected vs actual behavior
- Environment: Python version, OS, etc.
- Error logs or stack traces
- What you've tried to fix it

**Example:**

```
Title: Export validator fails on empty roots

Steps to reproduce:
1. Run: python 12_tooling/scripts/validate_public_boundary.py
2. With all denied roots empty
3. Validator exits with error

Expected: PASS (all critical gates)
Actual: FAIL on gate [5]

Environment: Python 3.11, Windows 11
Error: [stack trace]
```

## Security Issues

**DO NOT** report security issues publicly on GitHub.

Instead, email: [security@example.com](mailto:security@example.com)

Include:
- Description of vulnerability
- Affected component (which root/script)
- Steps to reproduce (if safe to share)
- Impact assessment

We will:
1. ✅ Acknowledge receipt within 24 hours
2. ✅ Confirm vulnerability
3. ✅ Develop fix privately
4. ✅ Release patch
5. ✅ Publish advisory (coordinated)

See [SECURITY.md](SECURITY.md) for full policy.

## Frequently Asked Questions

### Installation Issues

**Q: Import errors when running validators?**  
A: Ensure Python 3.10+ and dependencies installed: `pip install -r 12_tooling/requirements.txt`

**Q: Can I use SSID-open-core in production?**  
A: Yes! v0.1.0 is production-ready. See [CHANGELOG.md](CHANGELOG.md) for what's included.

**Q: How do I upgrade between versions?**  
A: Check [CHANGELOG.md](CHANGELOG.md) for breaking changes. Most updates are backward-compatible.

### API & Integration

**Q: Which Python versions are supported?**  
A: Python 3.10 and 3.11. We test on both.

**Q: Can I modify the 5 exported roots?**  
A: Yes! Fork, modify, and contribute via PR. See [CONTRIBUTING.md](CONTRIBUTING.md).

**Q: Can I contribute to the other 19 roots?**  
A: Those are private in canonical SSID. Contribute to canonical SSID instead. Only the 5 exported roots accept contributions here.

### Governance & Policy

**Q: How often is governance reviewed?**  
A: Quarterly. See [16_codex/GOVERNANCE_MAINTENANCE_PROCEDURES.md](16_codex/GOVERNANCE_MAINTENANCE_PROCEDURES.md).

**Q: Can the export boundary change?**  
A: Only via RFC + approval + ADR. See exception process in [16_codex/EXPORT_BOUNDARY.md](16_codex/EXPORT_BOUNDARY.md).

**Q: What's the difference between SSID-open-core and canonical SSID?**  
A: SSID-open-core is a certified 5-root derivative. Canonical SSID is the full 24-root implementation (private). See [README.md](README.md).

## Community Guidelines

We're committed to providing a welcoming environment. Please review:

- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) — Our community standards
- [CONTRIBUTING.md](CONTRIBUTING.md) — Contribution guidelines

## Recognition

We recognize contributors through:
- Release notes and credits
- CONTRIBUTORS.md file
- GitHub contributors page
- Periodic community highlights

## Roadmap

**What we're working on:**
- Phase 5: Enhanced documentation and examples (Q2 2026)
- Expanded API stability guarantees (v1.0.0)
- Community-contributed integrations and examples

**Want to influence priorities?**  
[Start a discussion](https://github.com/EduBrainBoost/SSID-open-core/discussions) or vote on [feature requests](https://github.com/EduBrainBoost/SSID-open-core/issues?labels=feature-request)!

## Still Need Help?

Try one of these:
1. **Search** [GitHub Issues](https://github.com/EduBrainBoost/SSID-open-core/issues) and [Discussions](https://github.com/EduBrainBoost/SSID-open-core/discussions)
2. **Ask** in [GitHub Discussions](https://github.com/EduBrainBoost/SSID-open-core/discussions)
3. **Email** [community@example.com](mailto:community@example.com)
4. **Report** security issues to [security@example.com](mailto:security@example.com)

---

**Thank you for being part of the SSID-open-core community!**
