#!/bin/bash
# Score Log Generator
# Version: 1.0
# Date: 2025-09-16

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

show_trend=false
output_file=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --trend)
            show_trend=true
            shift
            ;;
        --out)
            output_file="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Get current score
current_score=$("$ROOT_DIR/12_tooling/scripts/structure_guard.sh" score)
timestamp=$(date -Iseconds)
date_str=$(date +%Y%m%d)

# Create log entry
log_entry="{
  \"timestamp\": \"$timestamp\",
  \"date\": \"$date_str\",
  \"score\": $current_score,
  \"status\": \"$([ $current_score -ge 95 ] && echo "COMPLIANT" || echo "NON-COMPLIANT")\",
  \"compliance_level\": \"$([ $current_score -eq 100 ] && echo "MAXIMUM" || echo "PARTIAL")\"
}"

if [ -n "$output_file" ]; then
    # Ensure output directory exists
    mkdir -p "$(dirname "$output_file")"

    if $show_trend; then
        # Append to existing log file for trend analysis
        if [ -f "$output_file" ]; then
            echo "," >> "$output_file"
        else
            echo "[" > "$output_file"
        fi
        echo "$log_entry" >> "$output_file"

        # Close JSON array if this is a new file
        if [ $(wc -l < "$output_file") -eq 2 ]; then
            echo "]" >> "$output_file"
            # Fix JSON structure
            head -n -1 "$output_file" > "${output_file}.tmp"
            echo "$log_entry" >> "${output_file}.tmp"
            echo "]" >> "${output_file}.tmp"
            mv "${output_file}.tmp" "$output_file"
        else
            # Fix JSON structure for existing file
            head -n -2 "$output_file" > "${output_file}.tmp"
            echo ",$log_entry" >> "${output_file}.tmp"
            echo "]" >> "${output_file}.tmp"
            mv "${output_file}.tmp" "$output_file"
        fi
    else
        # Single entry
        echo "$log_entry" > "$output_file"
    fi

    echo "Score log written to: $output_file"
else
    echo "$log_entry"
fi

echo "Current compliance score: $current_score%"