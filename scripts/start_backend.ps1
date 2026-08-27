param(
    [string]$HostName = "127.0.0.1",
    [int]$Port = 8080,
    [string]$PythonExe = "",
    [switch]$KillExisting
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")

if (-not $PythonExe) {
    $ProjectVirtualEnvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
    if (Test-Path $ProjectVirtualEnvPython) {
        $PythonExe = $ProjectVirtualEnvPython
    }
    elseif (Test-Path "D:\python3.11\python.exe") {
        $PythonExe = "D:\python3.11\python.exe"
    } else {
        $PythonExe = "python"
    }
}

Write-Host "Starting GaitLogic Planner backend..." -ForegroundColor Cyan
Write-Host "Project root: $ProjectRoot"
Write-Host "Python: $PythonExe"
Write-Host "API: http://${HostName}:${Port}"
Write-Host "Docs: http://${HostName}:${Port}/docs"
Write-Host ""

Set-Location $ProjectRoot

if (-not $env:GAITLOGIC_GIT_COMMIT) {
    $detectedCommit = (& git -C $ProjectRoot rev-parse --short=12 HEAD 2>$null)
    if ($LASTEXITCODE -eq 0 -and $detectedCommit) {
        $env:GAITLOGIC_GIT_COMMIT = $detectedCommit.Trim()
    }
}

if ($KillExisting) {
    $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    $processIds = $connections | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($processId in $processIds) {
        if ($processId -and $processId -ne $PID) {
            Write-Host "Stopping existing process on port ${Port}: PID $processId" -ForegroundColor Yellow
            Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
        }
    }
}

& $PythonExe -m uvicorn server.main:app --reload --app-dir "$ProjectRoot" --host $HostName --port $Port
