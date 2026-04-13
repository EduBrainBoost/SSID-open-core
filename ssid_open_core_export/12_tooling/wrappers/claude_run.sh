#!/bin/bash
# Claude CLI Wrapper - SSID Tool Adapter v4.1
# Enforces LOG_MODE=MINIMAL and dispatcher-only execution

set -euo pipefail

# SSID Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DISPATCHER="$REPO_ROOT/24_meta_orchestration/dispatcher/dispatcher.py"

# Environment enforcement - SSID Data Minimization
export LOG_MODE="${LOG_MODE:-MINIMAL}"
export NO_PROMPT_PERSIST="true"
export NO_STDOUT_PERSIST="true"
export CLAUDE_TELEMETRY="false"
export CLAUDE_NO_HISTORY="true"

# Tool-specific configuration with telemetry blocking
CLAUDE_CLI="${CLAUDE_CLI:-claude}"
CLAUDE_ARGS="${CLAUDE_ARGS:---format text --no-telemetry --no-history}"

# Parse arguments
TASK_SPEC=""
ALLOWED_PATHS=""
PROMPT=""

show_help() {
    cat << EOF
SSID Claude CLI Wrapper v4.1

Usage: $0 --task <spec> [--prompt <prompt>] [--paths <paths>]
       $0 --help

Options:
  --task <spec>       Task specification (JSON/YAML)
  --prompt <prompt>   Custom prompt (overrides task spec)
  --paths <paths>     Comma-separated allowed paths
  --help              Show this help

All execution goes through dispatcher.py with LOG_MODE=MINIMAL.
EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --task)
            TASK_SPEC="$2"
            shift 2
            ;;
        --prompt)
            PROMPT="$2"
            shift 2
            ;;
        --paths)
            ALLOWED_PATHS="$2"
            shift 2
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            echo "ERROR: Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Validate required arguments
if [[ -z "$TASK_SPEC" ]]; then
    echo "ERROR: --task is required"
    show_help
    exit 1
fi

if [[ ! -f "$TASK_SPEC" ]]; then
    echo "ERROR: Task spec not found: $TASK_SPEC"
    exit 1
fi

# Ensure dispatcher exists
if [[ ! -f "$DISPATCHER" ]]; then
    echo "ERROR: Dispatcher not found: $DISPATCHER"
    exit 1
fi

# Prepare task spec updates
if [[ -n "$PROMPT" || -n "$ALLOWED_PATHS" ]]; then
    # Create temporary task spec with updates
    TEMP_SPEC=$(mktemp)
    trap "rm -f $TEMP_SPEC" EXIT
    
    if [[ "$TASK_SPEC" == *.yaml || "$TASK_SPEC" == *.yml ]]; then
        cp "$TASK_SPEC" "$TEMP_SPEC"
        if [[ -n "$PROMPT" ]]; then
            yaml-cli set "$TEMP_SPEC" prompt "$PROMPT"
        fi
        if [[ -n "$ALLOWED_PATHS" ]]; then
            # Convert comma-separated to array
            python3 -c "
import yaml, sys, json
with open('$TEMP_SPEC') as f: data = yaml.safe_load(f)
data['allowed_paths'] = [p.strip() for p in '$ALLOWED_PATHS'.split(',')]
with open('$TEMP_SPEC', 'w') as f: yaml.dump(data, f, default_flow_style=False)
"
        fi
        TASK_SPEC="$TEMP_SPEC"
    else
        # JSON
        python3 -c "
import json, sys
with open('$TASK_SPEC') as f: data = json.load(f)
if '$PROMPT': data['prompt'] = '$PROMPT'
if '$ALLOWED_PATHS': data['allowed_paths'] = [p.strip() for p in '$ALLOWED_PATHS'.split(',')]
with open('$TEMP_SPEC', 'w') as f: json.dump(data, f, indent=2)
"
        TASK_SPEC="$TEMP_SPEC"
    fi
fi

echo "INFO: SSID Claude Wrapper - Task: $(basename "$TASK_SPEC")"
echo "INFO: LOG_MODE=$LOG_MODE"
echo "INFO: Using dispatcher: $DISPATCHER"

# Create sandbox and get injected prompt
echo "INFO: Creating sandbox and preparing Claude execution..."
TASK_OUTPUT=$(python3 "$DISPATCHER" run --tool claude --task "$TASK_SPEC" --export-prompt)
SANDBOX_DIR=$(python3 "$DISPATCHER" run --tool claude --task "$TASK_SPEC" | grep "SANDBOX:" | cut -d' ' -f2)

# Execute Claude with injected prompt
echo "INFO: Executing Claude in sandbox: $SANDBOX_DIR"
echo "INFO: Claude CLI: $CLAUDE_CLI $CLAUDE_ARGS"

# Claude execution in sandbox
cd "$SANDBOX_DIR"
echo "$TASK_OUTPUT" | $CLAUDE_CLI $CLAUDE_ARGS

CLAUDE_EXIT_CODE=$?

if [[ $CLAUDE_EXIT_CODE -ne 0 ]]; then
    echo "ERROR: Claude execution failed with exit code: $CLAUDE_EXIT_CODE"
    exit $CLAUDE_EXIT_CODE
fi

# Package results with gates
echo "INFO: Claude execution completed, running gates and packaging..."
python3 "$DISPATCHER" package --task "$TASK_SPEC" --sandbox "$SANDBOX_DIR"
FINAL_EXIT_CODE=$?

if [[ $FINAL_EXIT_CODE -eq 0 ]]; then
    echo "SUCCESS: Claude task completed and packaged successfully"
else
    echo "ERROR: Claude task failed during gate validation"
fi

exit $FINAL_EXIT_CODE
