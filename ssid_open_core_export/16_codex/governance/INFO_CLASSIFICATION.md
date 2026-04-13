# INFO CLASSIFICATION

## Scope Mapping (Option A - Baseline Policy)

| Klasse | Darf Public | Inhalt | Pfade/Artefakte |
|--------|-------------|--------|-----------------|
| **PUBLIC** | ✅ | Kommunikation + high-level Governance ohne operative Details | `16_codex/roadmap/ROADMAP_PUBLIC.md`, `16_codex/governance/INFO_CLASSIFICATION.md`, `16_codex/decisions/ADR_*.md` (redacted/public-safe), SoT-Artefakte ohne Secrets |
| **INTERNAL** | ⚠️ (privat) | Ausführungs- und Steuerungsebene | `16_codex/roadmap/ROADMAP_INTERNAL.md`, `24_meta_orchestration/plans/*.yaml`, `24_meta_orchestration/plans/TASK_SPEC_MINIMAL.schema.yaml`, `24_meta_orchestration/queue/TASK_QUEUE.yaml`, `24_meta_orchestration/dispatcher/e2e_dispatcher.py`, `12_tooling/cli/*.py` (inkl. run_all_gates.py, Guards), `02_audit_logging/agent_runs/<run_id>/manifest.json` |
| **LOCAL-ONLY** | ❌ | Alles, was riskant oder nicht deterministisch auditierbar ist | `.ssid_sandbox/`, `.env*`, `*.pem`, `*.key`, `*.p12`, `*.jks`, `*.pfx`, `*.token`, `02_audit_logging/raw_logs/`, `02_audit_logging/agent_runs/*/patch.diff` (optional local), Secrets/Logs |

## Enforcement

### 1. .gitignore (Local-only hard)
```
.ssid_sandbox/
.env / .env.*
*.pem, *.key, *.p12, *.jks, *.pfx, *.token, *.secret*, *.secrets
02_audit_logging/agent_runs/
02_audit_logging/raw_logs/
12_tooling/cli/scorecard.json, 12_tooling/cli/scorecard.md
```

### 2. repo_separation_guard.py (Blocking)
- **Git-Mode**: scannt nur `git ls-files`
- **Non-Git-Mode**: scannt nur `patch.diff`
- **Exit-Codes**: `0` PASS, `2` Policy Violation, `3` Tooling Error
- **ADR-Pflicht**: Trigger-Pfade → ADR muss im Change-Set sein

### 3. CI (.github/workflows/gates.yml)
```yaml
steps:
  - uses: actions/checkout@v4 (fetch-depth: 0)
  - python 12_tooling/cli/repo_separation_guard.py --repo-root .
  - python 12_tooling/cli/run_all_gates.py
```

## Operative Regeln

1. Public Repo enthält keine Execution-Plans (bleibt INTERNAL)
2. Run-Logs nur minimal: nur `manifest.json` als Hash-Ledger
3. Alles Secret-ähnliche ist auto-blocked (Guard + .gitignore)
4. Governance/Process Änderungen brauchen ADR (Guard enforced)

## PUBLIC
- Safe for external publication.
- Must not include sensitive controls, secret material, or abuse paths.

## INTERNAL
- Operational project content for team execution.
- Not for public release without review.

## SENSITIVE
- Security-relevant internal details.
- Private handling only; redact before any external sharing.

## SECRET
- Credentials, private keys, tokens, seed phrases, and equivalent material.
- Never commit to repository under any circumstance.
