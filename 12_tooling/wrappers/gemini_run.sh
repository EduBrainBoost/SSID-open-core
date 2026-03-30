#!/bin/bash
# Gemini CLI Wrapper - SSID Tool Adapter v4.1
# Optimized for compliance auditing and documentation checks

set -euo pipefail

# SSID Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DISPATCHER="$REPO_ROOT/24_meta_orchestration/dispatcher/dispatcher.py"

# Environment enforcement - SSID Data Minimization
export LOG_MODE="${LOG_MODE:-MINIMAL}"
export NO_PROMPT_PERSIST="true"
export NO_STDOUT_PERSIST="true"
export GEMINI_TELEMETRY="false"
export GEMINI_NO_HISTORY="true"

# Tool-specific configuration with telemetry blocking
GEMINI_CLI="${GEMINI_CLI:-gemini}"
GEMINI_ARGS="${GEMINI_ARGS:---model gemini-pro --format analysis --no-telemetry --no-history}"

# Parse arguments
TASK_SPEC=""
ALLOWED_PATHS=""
PROMPT=""

show_help() {
    cat << EOF
SSID Gemini CLI Wrapper v4.1

Usage: $0 --task <spec> [--prompt <prompt>] [--paths <paths>]
       $0 --help

Options:
  --task <spec>       Task specification (JSON/YAML)
  --prompt <prompt>   Custom prompt (overrides task spec)
  --paths <paths>     Comma-separated allowed paths
  --help              Show this help

Optimized for compliance auditing and 2nd opinion reviews.
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

echo "INFO: SSID Gemini Wrapper - Task: $(basename "$TASK_SPEC")"
echo "INFO: LOG_MODE=$LOG_MODE"
echo "INFO: Using dispatcher: $DISPATCHER"

# Create sandbox and prepare execution
echo "INFO: Creating sandbox and preparing Gemini execution..."
TASK_OUTPUT=$(python3 "$DISPATCHER" run --tool gemini --task "$TASK_SPEC" --export-prompt)
SANDBOX_DIR=$(python3 "$DISPATCHER" run --tool gemini --task "$TASK_SPEC" | grep "SANDBOX:" | cut -d' ' -f2)

# Execute Gemini with injected prompt
echo "INFO: Executing Gemini in sandbox: $SANDBOX_DIR"
echo "INFO: Gemini CLI: $GEMINI_CLI $GEMINI_ARGS"

# Gemini execution in sandbox
cd "$SANDBOX_DIR"
echo "$TASK_OUTPUT" | $GEMINI_CLI $GEMINI_ARGS

GEMINI_EXIT_CODE=$?

if [[ $GEMINI_EXIT_CODE -ne 0 ]]; then
    echo "ERROR: Gemini execution failed with exit code: $GEMINI_EXIT_CODE"
    exit $GEMINI_EXIT_CODE
fi

# Package results with gates
echo "INFO: Gemini execution completed, running gates and packaging..."
python3 "$DISPATCHER" package --task "$TASK_SPEC" --sandbox "$SANDBOX_DIR"
FINAL_EXIT_CODE=$?

if [[ $FINAL_EXIT_CODE -eq 0 ]]; then
    echo "SUCCESS: Gemini task completed and packaged successfully"
else
    echo "ERROR: Gemini task failed during gate validation"
fi

exit $FINAL_EXIT_CODE
