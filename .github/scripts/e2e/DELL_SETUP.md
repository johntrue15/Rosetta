# Dell CI runner setup — Cursor agent playbook

Use this document when the Rosetta repo is cloned onto the Dell Windows machine
and you need to register the **persistent** GitHub Actions runner that powers
`watchdog-windows-e2e.yml`.

**Goal:** a self-hosted runner on `johntrue15/Rosetta` with:

- **Name:** `rosetta-ci-dell`
- **Label:** `rosetta-ci-dell`
- **Install dir:** `C:\rosetta-ci-runner`
- **Runs as:** Windows service (starts on boot)

This runner is **not** the per-facility runner created during each e2e test.
It only executes the `e2e-windows` job. Facility runners are created and
removed automatically by the test.

---

## Before you start

| Requirement | Notes |
|-------------|-------|
| Windows 10/11 | Local admin rights |
| PowerShell 5.1+ | Run **as Administrator** |
| Network | Outbound HTTPS to `github.com` and `rosetta.jtrue15.workers.dev` |
| GitHub CLI (`gh`) | Authenticated as a user who can admin `johntrue15/Rosetta` |
| Repo clone | Any path, e.g. `C:\Users\<user>\Documents\GitHub\Rosetta` |

Someone with repo admin access must also configure GitHub (Step 0) if not
already done.

---

## Step 0 — GitHub repository settings (admin, once)

These are **not** set on the Dell. Confirm in
https://github.com/johntrue15/Rosetta/settings :

**Secrets** (Settings → Secrets and variables → Actions → Secrets):

| Name | Value |
|------|-------|
| `ROSETTA_WORKER_URL` | `https://rosetta.jtrue15.workers.dev` |
| `ROSETTA_ONBOARD_HMAC_KEY` | Same string as Cloudflare Worker secret `ONBOARD_HMAC_KEY` |

**Variables** (Settings → Secrets and variables → Actions → Variables):

| Name | Value |
|------|-------|
| `ROSETTA_E2E_ENABLED` | `true` (set **after** the Dell runner is online) |

The Cloudflare Worker must be deployed with the latest `cloudflare/worker.js`
(`wrangler deploy` from a maintainer machine).

---

## Step 1 — Verify prerequisites

Open **PowerShell as Administrator** on the Dell.

```powershell
# Admin check
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) { throw "Re-open PowerShell as Administrator" }

# Python (required by deploy-watchdog on facility runners; good to verify on Dell)
python --version
# Expect: Python 3.9+

# Git (required for bash steps in deploy-watchdog)
git --version
# Expect: git version 2.x

# GitHub CLI
gh --version
gh auth status
# Expect: logged in to github.com with repo access to johntrue15/Rosetta
```

If Python is missing: install from https://www.python.org/downloads/ and check
**“Add Python to PATH”**.

If Git is missing: install https://git-scm.com/download/win (default options).

If `gh` is missing:

```powershell
winget install GitHub.cli
gh auth login
```

---

## Step 2 — Clone or update the repo

Skip if the repo is already cloned.

```powershell
$repoRoot = "C:\Users\$env:USERNAME\Documents\GitHub\Rosetta"
New-Item -ItemType Directory -Force -Path (Split-Path $repoRoot) | Out-Null
if (-not (Test-Path $repoRoot)) {
  git clone https://github.com/johntrue15/Rosetta.git $repoRoot
} else {
  git -C $repoRoot pull origin main
}
Set-Location $repoRoot
```

Adjust `$repoRoot` if the user cloned elsewhere. All later paths assume you
are in the repo root.

---

## Step 3 — Run the automated setup script

The script downloads `actions/runner`, registers it, and installs the Windows
service.

```powershell
Set-Location C:\path\to\Rosetta   # repo root

# Mint a short-lived registration token (expires in ~1 hour)
$token = gh api repos/johntrue15/Rosetta/actions/runners/registration-token `
  -X POST --jq .token

# Install the CI runner
.\.github\scripts\e2e\setup-ci-runner.ps1 -RegistrationToken $token
```

If `gh api` fails with 403, the authenticated user lacks admin access to the
repo. Use a maintainer account or generate a token manually:

1. Open https://github.com/johntrue15/Rosetta/settings/actions/runners/new
2. Select **Windows** → **x64**
3. Copy the `--token` value from the configure command (starts with something
   like `AAAA...`, not a PAT)
4. Run: `.\.github\scripts\e2e\setup-ci-runner.ps1 -RegistrationToken "PASTE_TOKEN_HERE"`

---

## Step 4 — Verify the runner is online

```powershell
# Local service
Get-Service | Where-Object { $_.Name -like "*actions.runner*" -or $_.DisplayName -like "*GitHub Actions Runner*" }

# GitHub API — should list rosetta-ci-dell as online
gh api repos/johntrue15/Rosetta/actions/runners --jq '.runners[] | {name, status, labels: [.labels[].name]}'
```

Expected output includes:

```json
{
  "name": "rosetta-ci-dell",
  "status": "online",
  "labels": ["self-hosted", "Windows", "X64", "rosetta-ci-dell"]
}
```

Also confirm at:
https://github.com/johntrue15/Rosetta/settings/actions/runners

---

## Step 5 — Enable and smoke-test the E2E workflow

1. Set repository variable `ROSETTA_E2E_ENABLED` = `true` (Step 0).
2. Trigger a test run:

```powershell
gh workflow run watchdog-windows-e2e.yml -R johntrue15/Rosetta
gh run list -R johntrue15/Rosetta -w "Watchdog Windows E2E" --limit 3
```

3. Watch the run: https://github.com/johntrue15/Rosetta/actions

**Pass criteria:**

- `provision` → green
- `e2e-windows` → green (ran on `rosetta-ci-dell`)
- `cleanup-github` → green
- No leftover issue titled `Facility request: E2E-Win-...`
- No leftover repo `rosetta-facility-e2e-win-...`

---

## Step 6 — Report back to the user

When finished, summarize:

- [ ] Python, Git, `gh` verified
- [ ] Runner service running at `C:\rosetta-ci-runner`
- [ ] `rosetta-ci-dell` shows **online** in GitHub
- [ ] `ROSETTA_E2E_ENABLED=true` set on the repo
- [ ] Smoke-test workflow run passed (link to run URL)

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `gh api ... registration-token` 403 | Log in as repo admin: `gh auth login` |
| Runner offline in GitHub | `cd C:\rosetta-ci-runner; .\svc.cmd status` then `.\svc.cmd start` |
| `config.cmd` fails “already configured” | Run setup with `-Replace` (script default) or delete `C:\rosetta-ci-runner` and re-run |
| E2E job queued forever | Runner label must be exactly `rosetta-ci-dell`; check Settings → Runners |
| `deploy-watchdog` fails inside e2e | Ensure Python + Git Bash on PATH for the **facility** runner (same machine, same PATH) |
| Worker 401 during bootstrap | Redeploy Cloudflare Worker; verify `ROSETTA_WORKER_URL` secret |

---

## Re-running setup (idempotent)

Safe to re-run after pulling repo updates:

```powershell
$token = gh api repos/johntrue15/Rosetta/actions/runners/registration-token -X POST --jq .token
.\.github\scripts\e2e\setup-ci-runner.ps1 -RegistrationToken $token
```

The script uses `--replace` so it reconfigures the existing runner in place.

---

## Uninstall (only if decommissioning the Dell)

```powershell
cd C:\rosetta-ci-runner
.\svc.cmd stop
.\svc.cmd uninstall
cd ..
Remove-Item -Recurse -Force C:\rosetta-ci-runner
```

Then remove the offline runner entry in GitHub → Settings → Actions → Runners.

---

## Related files

| File | Purpose |
|------|---------|
| [setup-ci-runner.ps1](./setup-ci-runner.ps1) | Automated runner install script |
| [README.md](./README.md) | E2E workflow overview |
| [watchdog-windows-e2e.yml](../../workflows/watchdog-windows-e2e.yml) | CI workflow definition |
| [cleanup-local.ps1](./cleanup-local.ps1) | Local teardown (called by CI, not setup) |
