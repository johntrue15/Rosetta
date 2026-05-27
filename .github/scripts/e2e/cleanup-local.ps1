# Remove Rosetta E2E artifacts from the Dell Windows machine.
param(
    [string]$RunnerDir = $env:ROSETTA_RUNNER_DIR,
    [string]$WatchPath = $env:ROSETTA_WATCH_PATH,
    [string]$ServiceName = "RosettaWatchdog"
)

$ErrorActionPreference = "Continue"

function Info($msg) { Write-Host "[e2e-cleanup] $msg" -ForegroundColor Cyan }

Info "Stopping watchdog service (if present)..."
$nssm = @(
    "$env:ProgramFiles\nssm\nssm.exe",
    "C:\rosetta-watchdog\nssm.exe",
    (Get-Command nssm -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source)
) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1

if ($nssm) {
    & $nssm stop $ServiceName 2>$null
    & $nssm remove $ServiceName confirm 2>$null
} else {
    sc.exe stop $ServiceName 2>$null
    sc.exe delete $ServiceName 2>$null
}

if ($RunnerDir -and (Test-Path $RunnerDir)) {
    Info "Stopping facility runner in $RunnerDir..."
    Push-Location $RunnerDir
    if (Test-Path ".\svc.cmd") {
        & .\svc.cmd stop 2>$null
        & .\svc.cmd uninstall 2>$null
    }
    Pop-Location
    Remove-Item -Recurse -Force $RunnerDir -ErrorAction SilentlyContinue
}

if ($WatchPath -and (Test-Path $WatchPath)) {
    Info "Removing watch path $WatchPath..."
    Remove-Item -Recurse -Force $WatchPath -ErrorAction SilentlyContinue
}

# Clear machine-level install ticket from prior runs
[Environment]::SetEnvironmentVariable("ROSETTA_INSTALL_TICKET", $null, "Machine")

Info "Local cleanup complete."
