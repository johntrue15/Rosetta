# Load cloudflare/credentials.env into the current PowerShell session.
# Usage (from repo root or cloudflare/):
#   . .\cloudflare\load-credentials.ps1

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$file = Join-Path $here "credentials.env"

if (-not (Test-Path $file)) {
    Write-Error @"
Missing $file

  copy cloudflare\credentials.example.env cloudflare\credentials.env
  # Edit credentials.env with CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID
"@
    return
}

Get-Content $file | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith("#")) { return }
    $eq = $line.IndexOf("=")
    if ($eq -lt 1) { return }
    $name = $line.Substring(0, $eq).Trim()
    $value = $line.Substring($eq + 1).Trim()
    if ($value.StartsWith('"') -and $value.EndsWith('"')) {
        $value = $value.Substring(1, $value.Length - 2)
    }
    Set-Item -Path "Env:$name" -Value $value
}

Write-Host "[cloudflare] Loaded credentials from credentials.env" -ForegroundColor Green
if (-not $env:CLOUDFLARE_API_TOKEN) { Write-Warning "CLOUDFLARE_API_TOKEN is empty" }
if (-not $env:CLOUDFLARE_ACCOUNT_ID) { Write-Warning "CLOUDFLARE_ACCOUNT_ID is empty" }
