# Contributing to SSID-open-core

Thank you for your interest in contributing to SSID-open-core!

## What You Can Contribute

- Public SDK improvements
- Public schema updates
- Reference adapter implementations
- Documentation and examples
- Test coverage for public interfaces
- Synthetic datasets (with proper license metadata)

## What You Cannot Contribute

- Private source code copies
- Internal implementation details
- Secrets, credentials, or PII
- Private infrastructure configurations
- Internal agent runtime code

## Contribution Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Make your changes
4. Run tests: `python -m pytest tests/ -v`
5. Run private leak scan: `python 12_tooling/scripts/verify_private_leakage.py`
6. Submit a pull request

## Code Style

- Python 3.10+
- Type hints required
- Docstrings for public interfaces
- No hardcoded secrets or paths

## License

All contributions are under the MIT License.

## Security

If you discover a security issue, please submit via GitHub Security Advisory — do not open a public issue.

See [SECURITY.md](SECURITY.md) for details.
