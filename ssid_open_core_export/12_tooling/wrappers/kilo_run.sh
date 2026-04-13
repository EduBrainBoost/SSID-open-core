#!/usr/bin/env bash
set -euo pipefail
export LOG_MODE="${LOG_MODE:-MINIMAL}"
python3 "$(dirname "$0")/../../12_tooling/cli/ssid_dispatcher.py" run --tool kilo "$@"
