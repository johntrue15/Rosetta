# Deploy Rosetta Upload Worker using cloudflare/credentials.env
# Run from anywhere:  .\cloudflare\deploy.ps1

param(
    [switch]$SecretsOnly,
    [switch]$Dev
)

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

. (Join-Path $PSScriptRoot "load-credentials.ps1")

if (-not $env:CLOUDFLARE_API_TOKEN -or -not $env:CLOUDFLARE_ACCOUNT_ID) {
    throw "Set CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID in cloudflare/credentials.env"
}

$wrangler = Get-Command npx -ErrorAction SilentlyContinue
if (-not $wrangler) { $wrangler = Get-Command wrangler -ErrorAction SilentlyContinue }
if (-not $wrangler) { throw "Install Node.js and run: npm install (from repo root)" }

function Invoke-Wrangler {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Args)
    & npx wrangler @Args
    if ($LASTEXITCODE -ne 0) { throw "wrangler failed: $($Args -join ' ')" }
}

$devVars = Join-Path $repoRoot ".dev.vars"
if ($SecretsOnly) {
    if (-not (Test-Path $devVars)) {
        throw "Missing $devVars — copy .dev.vars.example to .dev.vars and fill in GitHub secrets"
    }
    Write-Host "[cloudflare] Uploading Worker secrets from .dev.vars..." -ForegroundColor Cyan
    Invoke-Wrangler secret bulk $devVars
    Write-Host "[cloudflare] Secrets uploaded." -ForegroundColor Green
    exit 0
}

if ($Dev) {
    if (-not (Test-Path $devVars)) {
        Write-Warning ".dev.vars missing — wrangler dev may fail without secrets"
    }
    Write-Host "[cloudflare] Starting wrangler dev..." -ForegroundColor Cyan
    Invoke-Wrangler dev
    exit 0
}

Write-Host "[cloudflare] Deploying rosetta-upload worker..." -ForegroundColor Cyan
Invoke-Wrangler deploy
Write-Host "[cloudflare] Deploy complete: https://rosetta.jtrue15.workers.dev" -ForegroundColor Green
