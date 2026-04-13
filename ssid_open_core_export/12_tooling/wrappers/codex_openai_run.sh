#!/usr/bin/env bash
set -euo pipefail
TASK="${1:?task spec json}"
CMDLINE="${2:-codex}"
export LOG_MODE="${LOG_MODE:-MINIMAL}"
export CODEX_CLI_PROFILE="${CODEX_CLI_PROFILE:-12_tooling/cli/config/codex_openai_profile.yaml}"
python3 "$(dirname "$0")/../../12_tooling/cli/ssid_dispatcher.py" run --tool codex --task "$TASK" --cmdline "$CMDLINE"
