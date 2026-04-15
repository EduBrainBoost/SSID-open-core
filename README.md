# SSID-open-core

Open-source core identity and compliance framework for SSID protocol.

## Overview

SSID-open-core provides foundational components for:
- Identity verification and management (03_core)
- Compliance and audit logging (23_compliance)
- Orchestration and coordination (24_meta_orchestration)
- CLI tooling and utilities (12_tooling)
- Documentation and standards (16_codex)

## Quick Start

### Installation

```bash
git clone https://github.com/EduBrainBoost/SSID-open-core.git
cd SSID-open-core
pip install -e .
```

### Running Tests (if available)

```bash
# Test suite tests are included in respective roots
pytest --co -q  # List available tests
```

## Architecture

```
SSID-open-core/
├── 03_core/                    # Core business logic
├── 12_tooling/                 # CLI tools & utilities
├── 16_codex/                   # Documentation & standards
├── 23_compliance/              # Compliance & audit logging
├── 24_meta_orchestration/      # Orchestration & coordination
├── README.md                   # This file
├── CONTRIBUTING.md             # Contribution guidelines
└── LICENSE                     # Apache 2.0 license
```

## Features

- **Identity Management**: Core components for identity verification and lifecycle management
- **Compliance Framework**: Comprehensive audit logging and compliance verification
- **Event-Driven Architecture**: Decoupled component communication via events
- **Security Controls**: Hardened against common attack vectors
- **CLI Tooling**: Production-ready command-line utilities

## Documentation

- [Contributing Guidelines](CONTRIBUTING.md)
- [Compliance Framework](16_codex/compliance/)
- [Core Architecture](03_core/)
- [Tooling Documentation](12_tooling/)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on:
- Setting up development environment
- Running tests
- Submitting pull requests
- Code style and conventions

## License

SSID-open-core is licensed under the [Apache License 2.0](LICENSE).

## Status

**Release:** 0.1.0
**Export Date:** 2026-04-15
**Verification:** PHASE 2 SANIERUNG
**Ready for:** Development / Testnet Vorbereitung
**Mainnet:** NICHT BEREIT

## Support

- Issues: GitHub Issues
- Discussions: GitHub Discussions
- Documentation: See README.md and 16_codex/

---

**Last Updated:** 2026-04-13 14:12:48 UTC
