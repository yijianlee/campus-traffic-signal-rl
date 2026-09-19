param([switch]$Isolated)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    if ($Isolated) { python -m venv .venv }
    else { python -m venv --system-site-packages .venv }
    if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed.' }
}
& '.\.venv\Scripts\python.exe' -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
& '.\.venv\Scripts\python.exe' -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Dependency check failed.' }
& '.\.venv\Scripts\python.exe' -m traffic_rl doctor
if ($LASTEXITCODE -ne 0) { throw 'Environment check failed.' }

