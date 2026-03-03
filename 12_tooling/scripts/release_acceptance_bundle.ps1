Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Set-Location (Join-Path $PSScriptRoot "..\..")

$gateCmd = "python 12_tooling\cli\run_all_gates.py"
$testCmd = "python -m pytest -q"
$sotCmd  = "python 12_tooling\cli\sot_validator.py --verify-all"

Invoke-Expression $gateCmd
$gateExit = $LASTEXITCODE
Invoke-Expression $testCmd
$testExit = $LASTEXITCODE
Invoke-Expression $sotCmd
$sotExit = $LASTEXITCODE

if ($gateExit -ne 0 -or $testExit -ne 0 -or $sotExit -ne 0) {
    throw "ACCEPTANCE FAIL gate=$gateExit test=$testExit sot=$sotExit"
}

$utc = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$base = "02_audit_logging\storage\worm\RELEASE_ACCEPTANCE\$utc\release_acceptance"
New-Item -ItemType Directory -Force $base | Out-Null

git rev-parse HEAD | Out-File -Encoding utf8 -NoNewline "$base\head.txt"
git rev-parse --abbrev-ref HEAD | Out-File -Encoding utf8 -NoNewline "$base\branch.txt"
git status --porcelain | Out-File -Encoding utf8 "$base\git_status.txt"

python 12_tooling\cli\run_all_gates.py > "$base\run_all_gates.log" 2>&1
"$LASTEXITCODE" | Out-File -Encoding utf8 -NoNewline "$base\run_all_gates.exitcode"

python -m pytest -q > "$base\pytest.log" 2>&1
"$LASTEXITCODE" | Out-File -Encoding utf8 -NoNewline "$base\pytest.exitcode"

python 12_tooling\cli\sot_validator.py --verify-all > "$base\sot_verify_all.log" 2>&1
"$LASTEXITCODE" | Out-File -Encoding utf8 -NoNewline "$base\sot_verify_all.exitcode"

$gateExit2 = [int](Get-Content "$base\run_all_gates.exitcode" -Raw)
$testExit2 = [int](Get-Content "$base\pytest.exitcode" -Raw)
$sotExit2  = [int](Get-Content "$base\sot_verify_all.exitcode" -Raw)
$gs = Get-Content "$base\git_status.txt" -Raw

if ($gateExit2 -eq 0 -and $testExit2 -eq 0 -and $sotExit2 -eq 0 -and [string]::IsNullOrWhiteSpace($gs)) {
    "PASS" | Out-File -Encoding utf8 -NoNewline "$base\acceptance_verdict.txt"
} else {
    "FAIL" | Out-File -Encoding utf8 -NoNewline "$base\acceptance_verdict.txt"
}

$manifestPath = "$base\hash_manifest.sha256"
$items = Get-ChildItem -File $base | Where-Object { $_.Name -ne "hash_manifest.sha256" } | Sort-Object Name
$manifestLines = foreach ($item in $items) {
    $h = (Get-FileHash $item.FullName -Algorithm SHA256).Hash.ToLower()
    "{0}  {1}" -f $h, $item.Name
}
$manifestLines | Out-File -Encoding utf8 $manifestPath

$zipPath = "$base.zip"
Compress-Archive -Path "$base\*" -DestinationPath $zipPath -Force
(Get-FileHash $zipPath -Algorithm SHA256).Hash.ToLower() |
    Out-File -Encoding utf8 -NoNewline "$zipPath.sha256"

Write-Host "WORM bundle created:"
Write-Host "  $zipPath"
Write-Host "  sha256: $(Get-Content "$zipPath.sha256")"
Write-Host "  verdict: $(Get-Content "$base\acceptance_verdict.txt")"
