[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ServerHost,

    [Parameter(Mandatory = $true)]
    [string]$ServerUser,

    [int]$SshPort = 22,

    [string]$RemotePath = "/www/wwwroot/gaitlogic-planner",

    [string]$RemoteFrontendDir = "",

    [ValidateSet("supervisor", "systemd", "none")]
    [string]$ServiceManager = "supervisor",

    [string]$BackendService = "gaitlogic-planner",

    [string]$PythonExe = "python",

    [string]$NodeExe = "",

    [switch]$SkipTests,

    [switch]$SkipFrontendBuild,

    [switch]$SkipUpload,

    [switch]$SkipRemoteRestart,

    [switch]$RunInitDb,

    [switch]$ReloadNginx
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Text)
    Write-Host ""
    Write-Host "==> $Text" -ForegroundColor Cyan
}

function Assert-LastExit {
    param([string]$Name)
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE."
    }
}

function Assert-NoSingleQuote {
    param(
        [string]$Name,
        [string]$Value
    )
    if ($Value -and $Value.Contains("'")) {
        throw "$Name cannot contain a single quote because it is embedded in the remote shell script."
    }
}

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$DeployRoot = Join-Path $ProjectRoot ".deploy"
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$PackageName = "gaitlogic-planner-$Stamp"
$PackageDir = Join-Path $DeployRoot $PackageName
$PayloadDir = Join-Path $PackageDir "payload"
$ArchivePath = Join-Path $DeployRoot "$PackageName.zip"

if ([string]::IsNullOrWhiteSpace($RemoteFrontendDir)) {
    $RemoteFrontendDir = "$RemotePath/web-dist"
}

Assert-NoSingleQuote "RemotePath" $RemotePath
Assert-NoSingleQuote "RemoteFrontendDir" $RemoteFrontendDir
Assert-NoSingleQuote "BackendService" $BackendService
Assert-NoSingleQuote "ServiceManager" $ServiceManager
Assert-NoSingleQuote "PackageName" $PackageName

Write-Host "GaitLogic Planner deploy"
Write-Host "Project: $ProjectRoot"
Write-Host "Remote : ${ServerUser}@${ServerHost}:$RemotePath"
Write-Host "Static : $RemoteFrontendDir"

if (-not $SkipTests) {
    Write-Step "Run backend tests"
    Push-Location $ProjectRoot
    try {
        & $PythonExe -m pytest
        Assert-LastExit "pytest"
    }
    finally {
        Pop-Location
    }
}
else {
    Write-Step "Skip backend tests"
}

if (-not $SkipFrontendBuild) {
    Write-Step "Build frontend"
    Push-Location (Join-Path $ProjectRoot "web")
    try {
        if ([string]::IsNullOrWhiteSpace($NodeExe)) {
            if (Test-Path "D:\node21\node.exe") {
                $NodeExe = "D:\node21\node.exe"
            }
            elseif (Test-Path "D:\node18\node.exe") {
                $NodeExe = "D:\node18\node.exe"
            }
        }

        if (-not [string]::IsNullOrWhiteSpace($NodeExe)) {
            & $NodeExe "node_modules\vite\bin\vite.js" "build" "--config" "..\vite.web.config.mjs"
            Assert-LastExit "frontend build"
        }
        else {
            & npm run build
            Assert-LastExit "npm run build"
        }
    }
    finally {
        Pop-Location
    }
}
else {
    Write-Step "Skip frontend build"
}

Write-Step "Create deploy package"
New-Item -ItemType Directory -Force -Path $PayloadDir | Out-Null

$Directories = @(
    "server",
    "planner_core",
    "scripts",
    "sql",
    "docs",
    "web-dist"
)

foreach ($Directory in $Directories) {
    $Source = Join-Path $ProjectRoot $Directory
    if (Test-Path $Source) {
        Copy-Item -LiteralPath $Source -Destination $PayloadDir -Recurse -Force
    }
}

$Files = @(
    "pyproject.toml",
    ".env.example",
    "README.md",
    "README-EN.md",
    "vite.web.config.mjs"
)

foreach ($File in $Files) {
    $Source = Join-Path $ProjectRoot $File
    if (Test-Path $Source) {
        Copy-Item -LiteralPath $Source -Destination $PayloadDir -Force
    }
}

$PayloadItems = Get-ChildItem -LiteralPath $PayloadDir -Force
if (-not $PayloadItems) {
    throw "Deploy package is empty."
}

if (Test-Path $ArchivePath) {
    Remove-Item -LiteralPath $ArchivePath -Force
}

Compress-Archive -LiteralPath $PayloadItems.FullName -DestinationPath $ArchivePath -Force
Write-Host "Package: $ArchivePath"

if ($SkipUpload) {
    Write-Step "Skip upload"
    Write-Host "Deploy package is ready. Upload it manually if needed."
    exit 0
}

Write-Step "Check SSH tools"
if (-not (Get-Command ssh -ErrorAction SilentlyContinue)) {
    throw "ssh was not found. Install OpenSSH client or add it to PATH."
}
if (-not (Get-Command scp -ErrorAction SilentlyContinue)) {
    throw "scp was not found. Install OpenSSH client or add it to PATH."
}

Write-Step "Upload package"
$RemoteArchive = "/tmp/$PackageName.zip"
& scp -P $SshPort $ArchivePath "${ServerUser}@${ServerHost}:$RemoteArchive"
Assert-LastExit "scp upload"

$RunInitDbValue = if ($RunInitDb) { "1" } else { "0" }
$ReloadNginxValue = if ($ReloadNginx) { "1" } else { "0" }
$RestartValue = if ($SkipRemoteRestart) { "0" } else { "1" }

$RemoteScript = @'
set -euo pipefail

REMOTE_PATH='__REMOTE_PATH__'
REMOTE_FRONTEND_DIR='__REMOTE_FRONTEND_DIR__'
REMOTE_ARCHIVE='__REMOTE_ARCHIVE__'
PACKAGE_NAME='__PACKAGE_NAME__'
SERVICE_MANAGER='__SERVICE_MANAGER__'
BACKEND_SERVICE='__BACKEND_SERVICE__'
RUN_INIT_DB='__RUN_INIT_DB__'
RELOAD_NGINX='__RELOAD_NGINX__'
RESTART_BACKEND='__RESTART_BACKEND__'

WORK_DIR="/tmp/${PACKAGE_NAME}"
BACKUP_DIR="${REMOTE_PATH}/.deploy/backup-__STAMP__"

echo "Deploying to ${REMOTE_PATH}"
mkdir -p "${REMOTE_PATH}" "${REMOTE_PATH}/.deploy"
rm -rf "${WORK_DIR}"
mkdir -p "${WORK_DIR}" "${BACKUP_DIR}"
unzip -q -o "${REMOTE_ARCHIVE}" -d "${WORK_DIR}"

for item in server planner_core scripts sql docs pyproject.toml README.md README-EN.md .env.example vite.web.config.mjs web-dist; do
    if [ -e "${REMOTE_PATH}/${item}" ]; then
        cp -a "${REMOTE_PATH}/${item}" "${BACKUP_DIR}/"
    fi
done

for dir in server planner_core scripts sql docs; do
    if [ -d "${WORK_DIR}/${dir}" ]; then
        mkdir -p "${REMOTE_PATH}/${dir}"
        rsync -a --delete "${WORK_DIR}/${dir}/" "${REMOTE_PATH}/${dir}/"
    fi
done

for file in pyproject.toml README.md README-EN.md .env.example vite.web.config.mjs; do
    if [ -f "${WORK_DIR}/${file}" ]; then
        cp "${WORK_DIR}/${file}" "${REMOTE_PATH}/${file}"
    fi
done

if [ -d "${WORK_DIR}/web-dist" ]; then
    mkdir -p "${REMOTE_FRONTEND_DIR}"
    rsync -a --delete "${WORK_DIR}/web-dist/" "${REMOTE_FRONTEND_DIR}/"
fi

cd "${REMOTE_PATH}"
PYTHON_BIN=".venv/bin/python"
if [ ! -x "${PYTHON_BIN}" ]; then
    PYTHON_BIN="python3"
fi

"${PYTHON_BIN}" -m pip install -e .

if [ "${RUN_INIT_DB}" = "1" ]; then
    "${PYTHON_BIN}" scripts/init_db.py
fi

if [ "${RESTART_BACKEND}" = "1" ]; then
    if [ "${SERVICE_MANAGER}" = "supervisor" ]; then
        supervisorctl restart "${BACKEND_SERVICE}"
    elif [ "${SERVICE_MANAGER}" = "systemd" ]; then
        systemctl restart "${BACKEND_SERVICE}"
    fi
fi

if [ "${RELOAD_NGINX}" = "1" ]; then
    nginx -t
    nginx -s reload
fi

rm -rf "${WORK_DIR}" "${REMOTE_ARCHIVE}"
echo "Deploy finished. Backup: ${BACKUP_DIR}"
'@

$RemoteScript = $RemoteScript.Replace("__REMOTE_PATH__", $RemotePath)
$RemoteScript = $RemoteScript.Replace("__REMOTE_FRONTEND_DIR__", $RemoteFrontendDir)
$RemoteScript = $RemoteScript.Replace("__REMOTE_ARCHIVE__", $RemoteArchive)
$RemoteScript = $RemoteScript.Replace("__PACKAGE_NAME__", $PackageName)
$RemoteScript = $RemoteScript.Replace("__SERVICE_MANAGER__", $ServiceManager)
$RemoteScript = $RemoteScript.Replace("__BACKEND_SERVICE__", $BackendService)
$RemoteScript = $RemoteScript.Replace("__RUN_INIT_DB__", $RunInitDbValue)
$RemoteScript = $RemoteScript.Replace("__RELOAD_NGINX__", $ReloadNginxValue)
$RemoteScript = $RemoteScript.Replace("__RESTART_BACKEND__", $RestartValue)
$RemoteScript = $RemoteScript.Replace("__STAMP__", $Stamp)

Write-Step "Run remote deploy"
$RemoteScript | & ssh -p $SshPort "${ServerUser}@${ServerHost}" "bash -s"
Assert-LastExit "remote deploy"

Write-Step "Done"
Write-Host "Deployed $PackageName to ${ServerUser}@${ServerHost}:$RemotePath"
