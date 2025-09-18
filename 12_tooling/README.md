# 12_tooling

## Purpose

The Tooling module provides essential development tools, scripts, linters, generators, and git hooks to maintain code quality and structural integrity across the SSID OpenCore ecosystem.

## Key Features

- **Structure Guard**: Core validation script for 24-module structure
- **Pre-commit Hooks**: Automated validation before commits
- **Development Scripts**: Utility scripts for common development tasks
- **Code Generators**: Automated generation of boilerplate code and documentation
- **Linting Tools**: Code quality and compliance validation

## Critical Components

- `structure_guard.sh`: Primary structure validation with badge calculation
- `pre_commit/structure_validation.sh`: Git pre-commit validation hook
- Various utility scripts for development workflow

## Integration Points

- Provides validation tools for `23_compliance`
- Integrates with `24_meta_orchestration` CI/CD gates
- Used by all modules for development workflow