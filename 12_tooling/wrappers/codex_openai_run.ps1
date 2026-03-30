Param(
    [Parameter(Mandatory = $true)]
    [string]$Task,
    [Parameter(Mandatory = $false)]
    [string]$Cmdline = "codex"
)

$ErrorActionPreference = "Stop"
if (-not $env:LOG_MODE) { $env:LOG_MODE = "MINIMAL" }
if (-not $env:CODEX_CLI_PROFILE) {
    $env:CODEX_CLI_PROFILE = "12_tooling/cli/config/codex_openai_profile.yaml"
}

python 12_tooling/cli/ssid_dispatcher.py run --tool codex --task $Task --cmdline $Cmdline
