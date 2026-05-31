# Watchdog Windows E2E (Dell runner)

Automated end-to-end test that exercises the **real** Windows install path on the
Dell machine: facility issue → onboard → companion repo → bootstrap → self-hosted
facility runner → `deploy-watchdog.yml` → NSSM service → file upload → cleanup.

Workflow: [`.github/workflows/watchdog-windows-e2e.yml`](../../workflows/watchdog-windows-e2e.yml)

## Interactive device-flow E2E (what real operators do)

[`.github/workflows/watchdog-device-e2e.yml`](../../workflows/watchdog-device-e2e.yml)
tests the **download-and-run** path with the real **device OAuth** flow. It
provisions an approved facility, then on the Dell runner **prints a device code
and waits** (default 120s) for *you* to open <https://github.com/login/device>,
enter the code, and approve the Rosetta Upload app. It then mints the install
ticket, installs + runs the watchdog once, uploads a test scan, and confirms it
through the Worker dashboard endpoints (`/facility/data` + `/facility/status`)
before tearing everything down.

Run it manually and watch the live logs for the code:

```bash
gh workflow run watchdog-device-e2e.yml -f wait_seconds=120
# then: gh run watch $(gh run list -w watchdog-device-e2e.yml -L1 --json databaseId --jq '.[0].databaseId')
```

No repo variable needed — it's manual-only. Just requires the `rosetta-ci-dell`
runner (below) online and the `ROSETTA_WORKER_URL` secret set.

**Setting up the Dell for the first time?** A Cursor agent (or human) should
follow **[DELL_SETUP.md](./DELL_SETUP.md)** after cloning the repo onto the Dell.

## One-time Dell setup

The Dell hosts **two** runners during a test:

| Runner | Label | Purpose | Persists? |
|--------|-------|---------|-----------|
| CI orchestrator | `rosetta-ci-dell` | Runs the GitHub Actions e2e job steps | **Yes** — register once |
| Facility runner | `facility-e2e-win-<run_id>` | Created by bootstrap each test | **No** — removed in cleanup |

### 1. Install prerequisites on the Dell

- Windows 10/11 with Administrator access
- **Python 3.9+** on PATH (`python --version`)
- **Git for Windows** (bash for workflow steps)
- Outbound HTTPS to GitHub and the Rosetta Worker URL

### 2. Register the persistent CI runner

Prefer the automated script (see **[DELL_SETUP.md](./DELL_SETUP.md)**):

```powershell
$token = gh api repos/johntrue15/Rosetta/actions/runners/registration-token -X POST --jq .token
.\.github\scripts\e2e\setup-ci-runner.ps1 -RegistrationToken $token
```

Manual equivalent (PowerShell as Administrator):

```powershell
$ciDir = "C:\rosetta-ci-runner"
New-Item -ItemType Directory -Force -Path $ciDir | Out-Null
Set-Location $ciDir

# Download actions/runner (win-x64) from https://github.com/actions/runner/releases
# Then configure against johntrue15/Rosetta with label rosetta-ci-dell:
.\config.cmd --url https://github.com/johntrue15/Rosetta --token <REG_TOKEN> `
  --labels rosetta-ci-dell --name rosetta-ci-dell --unattended

.\svc.cmd install
.\svc.cmd start
```

Generate `<REG_TOKEN>` from **Rosetta → Settings → Actions → Runners → New self-hosted runner**.

### 3. Enable the workflow in GitHub

Repository **Settings → Secrets and variables → Actions**:

| Secret | Value |
|--------|-------|
| `ROSETTA_WORKER_URL` | `https://rosetta.jtrue15.workers.dev` |
| `ROSETTA_ONBOARD_HMAC_KEY` | Same as Worker `ONBOARD_HMAC_KEY` |

Repository **Variables**:

| Variable | Value |
|----------|-------|
| `ROSETTA_E2E_ENABLED` | `true` |

Deploy the updated Worker (`wrangler deploy`) before the first run so
`/workflow/dispatch-deploy`, `/e2e/cleanup`, and install-ticket auth are live.

## What each run does

1. **provision** (ubuntu): creates throwaway facility issue, labels `facility-approved`,
   waits for `data/e2e-win-<run_id>/config.yml`, creates companion repo via Worker,
   mints install ticket.
2. **e2e-windows** (Dell `rosetta-ci-dell`): runs bootstrap, waits for deploy,
   drops `example.pca`, verifies JSON upload.
3. **cleanup-github** (ubuntu, always): Worker deletes companion repo + facility
   files + issue; removes `users.csv` entry.
4. **cleanup-local** (Dell, always): stops `RosettaWatchdog`, removes facility
   runner dir and watch folder.

## Manual trigger

```bash
gh workflow run watchdog-windows-e2e.yml -R johntrue15/Rosetta
```

Or push to `main` under `edge/**`.

## Troubleshooting

| Symptom | Likely cause |
|---------|----------------|
| Job queued forever on `e2e-windows` | Dell CI runner offline or missing `rosetta-ci-dell` label |
| `deploy-watchdog` fails | Git Bash missing; Python not on PATH for facility runner |
| Upload timeout | Watch path mismatch — check issue body watch path vs copied file |
| Worker 401 on bootstrap | Worker not deployed with install-ticket auth fix |
| `ROSETTA_E2E_ENABLED` skipped | Set repo variable to `true` |

## Disable without removing the Dell runner

Set repository variable `ROSETTA_E2E_ENABLED` to `false` (or delete it). The
workflow will skip all jobs.
