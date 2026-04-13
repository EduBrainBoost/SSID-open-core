# Local Verification Quickstart

**SSID-open-core Local Verification** is the canonical verification path. No GitHub runners, no cloud costs, 100% local.

## Requirements

- Python 3.11+
- ruff (installed via `pip install .[dev]`)
- pyyaml

## Windows (PowerShell)

```powershell
# Install dependencies
pip install -e .[dev]

# Run local verification
python 12_tooling/cli/local_verify.py
```

Expected output on PASS:
```
======================================================================
SSID-open-core Local Verification (Zero-Cost, Local-Only)
======================================================================

[Ruff Lint]
PASS: ruff lint check ...

[Ruff Format]
PASS: ruff format check ...

[Module YAML]
PASS: all module.yaml files valid

[Export Policy]
PASS: export policy valid (version 2.0.0)

[Deny Globs]
PASS: no deny-glob violations

[Secret Scan]
PASS: no secret patterns detected

[Structure]
PASS: all 5 exported roots have required files

======================================================================
VERIFICATION PASS: All gates green ✅
======================================================================
```

Exit code: `0`

## Linux / Mac (Git Bash)

```bash
# Install dependencies
pip install -e ".[dev]"

# Run local verification
python 12_tooling/cli/local_verify.py
```

Same output as above. Exit code: `0`

## Exit Codes

- `0` = All verification gates PASS ✅
- `1` = At least one gate FAILED ❌

## What's Verified

1. **Ruff Lint** — Code style conformance
2. **Ruff Format** — Code formatting standards
3. **Module YAML** — All module.yaml files are valid and complete
4. **Export Policy** — opencore_export_policy.yaml is valid
5. **Deny Globs** — No files match deny patterns (secrets, internals, etc.)
6. **Secret Scan** — No credential patterns detected in code
7. **Structure** — All 5 exported roots (03_core, 12_tooling, 16_codex, 23_compliance, 24_meta_orchestration) have required files

## This Verification Is

✅ **Local only** — No external services  
✅ **Zero cost** — No GitHub billing, no cloud runners  
✅ **Deterministic** — Same result every run  
✅ **Fast** — < 30 seconds typically  

## GitHub Workflows Are Optional

The remaining GitHub workflows (codeql, scorecard, secret-scan, public_export_integrity) are optional public-release tools.
They are NOT required for local readiness or internal verification.

**Canonical verification is local only.**
