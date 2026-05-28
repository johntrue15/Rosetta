# Rosetta — agent instructions

## Dell Windows CI runner setup

When working on the **Dell** machine with a fresh `git clone` of this repo,
register the persistent GitHub Actions runner used by watchdog E2E tests.

**Follow this playbook exactly:**

→ [`.github/scripts/e2e/DELL_SETUP.md`](.github/scripts/e2e/DELL_SETUP.md)

Quick command (PowerShell **as Administrator**, from repo root):

```powershell
$token = gh api repos/johntrue15/Rosetta/actions/runners/registration-token -X POST --jq .token
.\.github\scripts\e2e\setup-ci-runner.ps1 -RegistrationToken $token
```

Then verify the runner is online and run a smoke test per DELL_SETUP.md Step 4–5.

## Other agent tasks

| Task | Where to look |
|------|----------------|
| Watchdog E2E CI overview | [`.github/scripts/e2e/README.md`](.github/scripts/e2e/README.md) |
| Cloudflare Worker secrets / deploy | [`cloudflare/README.md`](cloudflare/README.md) |
| Edge watchdog development | [`edge/README.md`](edge/README.md) |
| Facility setup wizard | [`docs/setup-facility/`](docs/setup-facility/) |
| **Dev install test (`?dev=1`)** | [`docs/setup-facility/DEV.md`](docs/setup-facility/DEV.md) |
