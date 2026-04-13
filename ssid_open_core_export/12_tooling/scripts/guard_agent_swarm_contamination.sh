# DEPRECATED: REDUNDANT — Canonical tool is 03_core/validators/base_guard.py
#!/usr/bin/env bash
# Guard against agent-swarm repo contamination
FAIL=0

# Check for stale setup references
if grep -rl "agent-swarm setup" --include="*.md" --include="*.yaml" --include="*.json" . 2>/dev/null | grep -v node_modules; then
    echo "FAIL: stale 'agent-swarm setup' reference found"
    FAIL=1
fi

# Check for repo-local agent-swarm dirs
if [ -d ".agent-swarm" ]; then
    echo "FAIL: .agent-swarm directory in repo"
    FAIL=1
fi

# Check for Program Files CWD references
if grep -rl "Program Files.Git" --include="*.md" --include="*.sh" --include="*.ps1" . 2>/dev/null | grep -v node_modules; then
    echo "FAIL: Program Files/Git CWD reference found"
    FAIL=1
fi

exit $FAIL
