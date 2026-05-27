# Install the persistent rosetta-ci-dell GitHub Actions runner on this Windows machine.
#
# Usage (PowerShell as Administrator):
#   $token = gh api repos/johntrue15/Rosetta/actions/runners/registration-token -X POST --jq .token
#   .\.github\scripts\e2e\setup-ci-runner.ps1 -RegistrationToken $token
#
# See DELL_SETUP.md for the full Cursor agent playbook.

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$RegistrationToken,

    [string]$RunnerDir = "C:\rosetta-ci-runner",
    [string]$RunnerName = "rosetta-ci-dell",
    [string]$RunnerLabel = "rosetta-ci-dell",
    [string]$RepoUrl = "https://github.com/johntrue15/Rosetta"
)

$ErrorActionPreference = "Stop"

function Info($msg)  { Write-Host "[setup-ci-runner] $msg" -ForegroundColor Cyan }
function Fail($msg)  { Write-Host "[setup-ci-runner] ERROR: $msg" -ForegroundColor Red; exit 1 }

# --- Admin check ---
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator
)
if (-not $isAdmin) { Fail "Run this script in PowerShell as Administrator." }

# --- Prerequisite checks (warn only for python/git — facility deploy needs them on this machine) ---
foreach ($cmd in @("python", "git")) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        Write-Warning "$cmd not found on PATH. Install before running E2E tests (see DELL_SETUP.md)."
    } else {
        Info "$cmd OK: $(& $cmd --version 2>&1 | Select-Object -First 1)"
    }
}

# --- Prepare runner directory ---
Info "Runner directory: $RunnerDir"
New-Item -ItemType Directory -Force -Path $RunnerDir | Out-Null
Set-Location $RunnerDir

# --- Download actions/runner if not already present ---
if (-not (Test-Path ".\config.cmd")) {
    Info "Downloading latest actions/runner (win-x64)..."
    $release = Invoke-RestMethod -Uri "https://api.github.com/repos/actions/runner/releases/latest"
    $asset = $release.assets | Where-Object { $_.name -match "^actions-runner-win-x64-.*\.zip$" } | Select-Object -First 1
    if (-not $asset) { Fail "Could not find win-x64 runner asset in latest release." }

    $zipPath = Join-Path $RunnerDir "runner.zip"
    Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $zipPath
    Expand-Archive -Path $zipPath -DestinationPath $RunnerDir -Force
    Remove-Item $zipPath -Force
    Info "Runner binaries extracted."
} else {
    Info "Runner binaries already present — reconfiguring in place."
}

# --- Stop existing service before reconfigure ---
if (Test-Path ".\svc.cmd") {
    Info "Stopping existing runner service (if any)..."
    & .\svc.cmd stop 2>$null
}

# --- Configure runner ---
Info "Configuring runner '$RunnerName' with label '$RunnerLabel'..."
& .\config.cmd --unattended `
    --url $RepoUrl `
    --token $RegistrationToken `
    --name $RunnerName `
    --labels $RunnerLabel `
    --replace

# --- Install and start Windows service ---
Info "Installing runner as a Windows service..."
& .\svc.cmd install
& .\svc.cmd start

Start-Sleep -Seconds 5

# --- Verify service is running ---
$svc = Get-Service | Where-Object {
    $_.Name -like "*actions.runner*" -or $_.DisplayName -like "*GitHub Actions Runner*"
} | Select-Object -First 1

if ($svc -and $svc.Status -eq "Running") {
    Info "Runner service '$($svc.Name)' is Running."
} else {
    Fail "Runner service did not start. Check $RunnerDir\_diag\ for logs."
}

Info "Setup complete."
Info "Verify online: gh api repos/johntrue15/Rosetta/actions/runners --jq '.runners[] | {name, status, labels: [.labels[].name]}'"
Info "Then set ROSETTA_E2E_ENABLED=true on the repo and run: gh workflow run watchdog-windows-e2e.yml -R johntrue15/Rosetta"
