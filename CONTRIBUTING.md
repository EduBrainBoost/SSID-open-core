# Contributing to SSID-open-core

## WICHTIGE BOUNDARY REGELN (VOR DEM BEITRAG LESEN)

✅ Dieses Repo ist eine kuratierte public-safe Export-Oberfläche. Es ist KEIN Dump des privaten SSID Repos.
✅ Nur Inhalte aus der offiziellen Allowlist sind erlaubt.
✅ Keine operativen Runtime Dateien, Registry, Report Bus, Evidence, Caches oder Backups.
✅ Alle Änderungen werden automatisch auf Boundary Verstöße geprüft.

## Getting Started

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes
4. Add tests for new functionality
5. Run tests: `pytest`
6. Commit changes: `git commit -m "feature: description"`
7. Push to fork: `git push origin feature/your-feature`
8. Open a pull request

## Code Style

- **Python**: PEP 8 compliant
- **Markdown**: Standard conventions
- **Commits**: Conventional Commits format

## Testing

All changes should include tests. Minimum coverage: 80% for new code.

```bash
pytest --cov=. --cov-report=term-missing
```

## Pull Request Process

1. Update documentation as needed
2. Add tests for new features
3. Ensure all tests pass locally
4. Request code review from maintainers
5. Address review feedback
6. Maintainers will review and merge

## Reporting Issues

Please use GitHub Issues to report:
- Bugs
- Feature requests
- Documentation improvements
- Security concerns

Include:
- Description of issue
- Steps to reproduce (for bugs)
- Expected vs. actual behavior
- Environment details

## Code of Conduct

Be respectful, inclusive, and constructive in all interactions.

## License

All contributions are licensed under the Apache License 2.0.
