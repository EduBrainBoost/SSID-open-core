# SSID-open-core Local-Only Verification Policy

**Effective:** 2026-04-13  
**Status:** CANONICAL  

---

## Policy Statement

**SSID-open-core verification is local-only and zero-cost.**

GitHub Actions runners are not canonical for SSID-open-core readiness verification.
All critical gates run locally via `12_tooling/cli/local_verify.py`.

---

## Canonical Verification Path

### Entry Point
```bash
python 12_tooling/cli/local_verify.py
```

### Exit Code Contract
- **0** = Repository is VERIFIED and ready for:
  - Commit
  - Merge
  - Release
  - Public deployment

- **1** = Repository has failures. Fix and retry.

---

## What's Canonical

| Gate | Canonical | GitHub Optional |
|------|-----------|-----------------|
| Ruff Lint | ✅ Local | GitHub (deprecated) |
| Ruff Format | ✅ Local | GitHub (deprecated) |
| Module YAML validation | ✅ Local | GitHub (deprecated) |
| Export policy validation | ✅ Local | GitHub (deprecated) |
| Deny-glob enforcement | ✅ Local | GitHub (deprecated) |
| Secret scanning | ✅ Local | GitHub (optional) |
| Structure verification | ✅ Local | GitHub (deprecated) |

---

## What GitHub Workflows Remain (Optional Only)

- **codeql.yml** — Optional: Security analysis for public communication
- **scorecard.yml** — Optional: Dependency health for public metrics
- **secret-scan.yml** — Optional: Third-party scanning for transparency
- **public_export_integrity.yml** — Optional: CI documentation

**None of these are required for readiness.**

---

## Removed Workflows

The following GitHub-runner dependent workflows have been removed:

- `open_core_ci.yml` — Replaced by `local_verify.py` (all functionality)
- `cron_daily_sanctions.yml` — Not part of export verification
- `cron_daily_structure_gate.yml` — Replaced by `local_verify.py`
- `cron_quarterly_audit.yml` — Audit gates run locally on demand

---

## Cost Impact

### Before (GitHub-dependent)
- CI runner minutes per run: 5–10 minutes
- Cron jobs: 3× weekly (weekly at minimum)
- Monthly cost: ~$50–200 depending on plan

### After (Local-only)
- Verification time: < 30 seconds locally
- Monthly cost: **$0**

---

## When Local Verification Is Sufficient

✅ **Development:** Running tests, merging branches  
✅ **Pre-commit:** Linting, formatting, validation  
✅ **Tag creation:** Verify repo state before release tag  
✅ **Readiness assessment:** Determine if repo is deployable  

---

## When GitHub Workflows Are Optional

🔵 **Public release communication:** Use scorecard.yml for transparency  
🔵 **External dependency audits:** Use codeql.yml for public reports  
🔵 **Third-party integrations:** Use public_export_integrity.yml for GitHub marketplace  

**None of these block internal readiness.**

---

## Enforcement

1. **All PRs must pass `local_verify.py` before merge.**
   - Gate: Mandatory
   - Cost: $0
   - Time: < 30 seconds

2. **GitHub workflows are documentation only.**
   - No merge blocking
   - No cost blocking
   - No approval blocking

3. **CI gates in canonical main must be local-compatible.**
   - Any CI gate that cannot run locally is removed
   - Any gate that requires GitHub runners is deprecated

---

## Process

### Before Committing
```bash
python 12_tooling/cli/local_verify.py
```

### Before Merging
```bash
# In PR:
# - Local verify must PASS (required by PR template)
# - GitHub optional workflows may run (not required)
```

### Before Release
```bash
# Ensure local verification PASS
python 12_tooling/cli/local_verify.py

# Tag release (optional: GitHub workflows run as public artifacts)
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin vX.Y.Z
```

---

## Governance

This policy is maintained by SSID-open-core maintainers.

**Any change to this policy requires:**
1. Rationale documentation
2. Cost-benefit analysis
3. Maintainer consensus
4. Commit to git history

**No external approvals are required for local verification policy.**

---

## FAQ

**Q: Do I need to run GitHub workflows locally?**  
A: No. GitHub workflows are optional. Local verification is canonical.

**Q: Can I disable GitHub workflows?**  
A: Yes. They are not required for readiness. Optional workflows run automatically on push/PR.

**Q: What if a GitHub workflow fails?**  
A: GitHub workflows are optional. Your code is ready if local verification passes.

**Q: Can external teams block my commit based on GitHub workflows?**  
A: No. Readiness is determined by local verification only.

---

## Related Documents

- [LOCAL_VERIFICATION_QUICKSTART.md](LOCAL_VERIFICATION_QUICKSTART.md) — How to run local verification
- [12_tooling/cli/local_verify.py](12_tooling/cli/local_verify.py) — Verification source code
