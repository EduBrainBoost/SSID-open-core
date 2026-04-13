#!/bin/bash
# OpenCode CLI Wrapper - SSID Tool Adapter v4.1
# General-purpose tool for various development tasks

set -euo pipefail

# SSID Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DISPATCHER="$REPO_ROOT/12_tooling/cli/ssid_dispatcher.py"

# Environment enforcement - SSID Data Minimization
export LOG_MODE="${LOG_MODE:-MINIMAL}"
export NO_PROMPT_PERSIST="true"
export NO_STDOUT_PERSIST="true"
export OPENCODE_TELEMETRY="false"
export OPENCODE_NO_HISTORY="true"

# Tool-specific configuration with telemetry blocking
OPENCODE_CLI="${OPENCODE_CLI:-opencode}"
OPENCODE_ARGS="${OPENCODE_ARGS:---format text --no-telemetry --no-history}"

# Parse arguments
TASK_SPEC=""
ALLOWED_PATHS=""
PROMPT=""

show_help() {
    cat << EOF
SSID OpenCode CLI Wrapper v4.1

Usage: $0 --task <spec> [--prompt <prompt>] [--paths <paths>]
       $0 --help

Options:
  --task <spec>       Task specification (JSON/YAML)
  --prompt <prompt>   Custom prompt (overrides task spec)
  --paths <paths>     Comma-separated allowed paths
  --help              Show this help

General-purpose tool for development tasks.
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
    TEMP_SPEC=$(mktemp)
    trap "rm -f $TEMP_SPEC" EXIT
    
    if [[ "$TASK_SPEC" == *.yaml || "$TASK_SPEC" == *.yml ]]; then
        cp "$TASK_SPEC" "$TEMP_SPEC"
        if [[ -n "$PROMPT" ]]; then
            python3 -c "
import yaml
with open('$TEMP_SPEC') as f: data = yaml.safe_load(f)
data['prompt'] = '''$PROMPT'''
with open('$TEMP_SPEC', 'w') as f: yaml.dump(data, f, default_flow_style=False)
"
        fi
        if [[ -n "$ALLOWED_PATHS" ]]; then
            python3 -c "
import yaml
with open('$TEMP_SPEC') as f: data = yaml.safe_load(f)
data['allowed_paths'] = [p.strip() for p in '$ALLOWED_PATHS'.split(',')]
with open('$TEMP_SPEC', 'w') as f: yaml.dump(data, f, default_flow_style=False)
"
        fi
        TASK_SPEC="$TEMP_SPEC"
    else
        # JSON
        python3 -c "
import json
with open('$TASK_SPEC') as f: data = json.load(f)
if '$PROMPT': data['prompt'] = '''$PROMPT'''
if '$ALLOWED_PATHS': data['allowed_paths'] = [p.strip() for p in '$ALLOWED_PATHS'.split(',')]
with open('$TEMP_SPEC', 'w') as f: json.dump(data, f, indent=2)
"
        TASK_SPEC="$TEMP_SPEC"
    fi
fi

echo "INFO: SSID OpenCode Wrapper - Task: $(basename "$TASK_SPEC")"
echo "INFO: LOG_MODE=$LOG_MODE"
echo "INFO: Using dispatcher: $DISPATCHER"

# Create sandbox and prepare execution
echo "INFO: Creating sandbox and preparing OpenCode execution..."
TASK_OUTPUT=$(python3 "$DISPATCHER" run --tool opencode --task "$TASK_SPEC" --export-prompt)
SANDBOX_DIR=$(python3 "$DISPATCHER" run --tool opencode --task "$TASK_SPEC" | grep "SANDBOX:" | cut -d' ' -f2)

# Execute OpenCode with injected prompt
echo "INFO: Executing OpenCode in sandbox: $SANDBOX_DIR"
echo "INFO: OpenCode CLI: $OPENCODE_CLI $OPENCODE_ARGS"

# OpenCode execution in sandbox
cd "$SANDBOX_DIR"
echo "$TASK_OUTPUT" | $OPENCODE_CLI $OPENCODE_ARGS

OPENCODE_EXIT_CODE=$?

if [[ $OPENCODE_EXIT_CODE -ne 0 ]]; then
    echo "ERROR: OpenCode execution failed with exit code: $OPENCODE_EXIT_CODE"
    exit $OPENCODE_EXIT_CODE
fi

# Package results with gates
echo "INFO: OpenCode execution completed, running gates and packaging..."
python3 "$DISPATCHER" package --task "$TASK_SPEC" --sandbox "$SANDBOX_DIR"
FINAL_EXIT_CODE=$?

if [[ $FINAL_EXIT_CODE -eq 0 ]]; then
    echo "SUCCESS: OpenCode task completed and packaged successfully"
else
    echo "ERROR: OpenCode task failed during gate validation"
fi

exit $FINAL_EXIT_CODE
