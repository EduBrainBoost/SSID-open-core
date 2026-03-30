> DEPRECATED: Historical reference only.
> Canonical entrypoint: `python 12_tooling/cli/ssid_dispatcher.py ...`
> Canonical dispatcher (internal): `24_meta_orchestration/dispatcher/e2e_dispatcher.py`

# Quick Reference - SSID Agent Governance Stack

## 🎯 For Each Tool: Same Pattern

```bash
export LOG_MODE=MINIMAL
./12_tooling/wrappers/{TOOL}_run.sh <task_spec.json> "<tool_command>"
```

---

## 📋 Tool Reference

| Tool | Wrapper | Requires | Command |
|------|---------|----------|---------|
| **Gemini** | gemini_run.sh | Google API key | `gemini_run.sh task.json "generate code"` |
| **Copilot/Claude** | claude_run.sh | GitHub/Anthropic key | `claude_run.sh task.json "write tests"` |
| **OpenAI Codex** | codex_run.sh | OpenAI API key | `codex_run.sh task.json "refactor"` |
| **Kilo** | kilo_run.sh | (local/free) | `kilo_run.sh task.json "complete"` |
| **OpenCode AI** | opencode_run.sh | (local/free) | `opencode_run.sh task.json "debug"` |

---

## 🔐 Security (All Tools)

```
User Input
  ↓
Wrapper (LOG_MODE=MINIMAL)
  ↓
ssid_dispatcher.py
  ├─ Load task spec (allowed_paths)
  ├─ Create sandbox (.ssid_sandbox/{task_id}/)
  ├─ Run agent via adapter
  ├─ Extract patch (allowed_paths ONLY)
  └─ Run Gates:
     ├─ Write-Gate (hard-fail ❌ outside allowed_paths)
     ├─ Policy Gate
     ├─ SoT Gate (5 validators)
     └─ QA Gate
  ↓
Evidence Bundle (hash-only)
  ├─ gate_status.json
  ├─ patch.diff
  ├─ manifest.json
  └─ (NO: prompts/stdout/outputs)
  ↓
Exit Code: 0 (PASS) or 24 (FAIL)
```

---

## 📁 Key Paths

```
Wrappers:        12_tooling/wrappers/
Dispatcher:      24_meta_orchestration/dispatcher/e2e_dispatcher.py
Adapters:        12_tooling/cli/adapters/
Profiles:        16_codex/agents/TOOL_PROFILES/
Validators:      03_core/validators/sot/
Policies:        23_compliance/policies/sot/
Contracts:       16_codex/contracts/sot/
Evidence:        02_audit_logging/evidence/task_runs/
Sandboxes:       .ssid_sandbox/{task_id}/
```

---

## ✅ Verification Commands

```bash
# Check all SoT validators pass
python3 12_tooling/cli/sot_validator.py --verify-all

# Generate scorecard
python3 12_tooling/cli/sot_validator.py --scorecard

# Run gate chain (dry-run)
python3 12_tooling/cli/run_all_gates.py --dry-run

# View evidence for a task
ls -la 02_audit_logging/evidence/task_runs/
```

---

## 🚨 Important

- **LOG_MODE=MINIMAL**: Always set (prevents data exfiltration)
- **allowed_paths**: Task spec controls which files can be modified
- **Write-Gate**: Hard-fail outside allowed_paths (no override)
- **Evidence**: Hash-only, never commit prompts/outputs
- **Sandbox**: Always cleaned up after task completion
- **NO direct tool calls**: Everything through ssid_dispatcher.py

---

## 📞 If Something Breaks

1. Check `16_codex/agents/FAILURES.md` (append-only log)
2. Review evidence in `02_audit_logging/evidence/task_runs/`
3. Run `sot_validator.py --verify-all` for rule violations
4. Check gate_status.json for which gate failed
5. Review tool profile docs in `16_codex/agents/TOOL_PROFILES/`

---

**Version**: v3.2.0 | **Status**: Production Ready ✅
