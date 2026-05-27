# Rosetta Edge Watchdog

Standalone service that monitors Xradia / Phoenix CT scanner output
directories for new `.txrm` / `.pca` files, extracts metadata, and pushes it
to the Rosetta GitHub repository for aggregation.

## Recommended install — Setup Facility wizard (no PAT, no clone)

Go to **<https://johntrue15.github.io/Rosetta/docs/setup-facility/>** and
follow the wizard. After approval Step 4 will:

1. Run a device-code flow against the **Rosetta Upload** GitHub App
   (you type a short code at `github.com/login/device` — no token to copy).
2. Auto-create your private `johntrue15/rosetta-facility-<slug>` companion
   repo, which owns a self-hosted GitHub Actions runner on your CT machine.
3. Give you a single PowerShell / bash one-liner. Paste it as administrator
   on the CT machine — the script downloads the runner, registers it, and
   triggers `deploy-watchdog.yml` which installs the watchdog as a service.

After that the runner self-updates (`actions/runner` built-in) and the
companion repo's daily `update-watchdog.yml` redeploys the watchdog
whenever upstream `edge/` changes. The watchdog itself never holds a PAT —
it refreshes a 1-hour GitHub App installation token from the Cloudflare
Worker before each push.

See `cloudflare/README.md` for the Worker + GitHub App configuration that
backs this flow.

## Legacy manual install (still supported)

If you prefer not to use the wizard / runner, you can run the watchdog
yourself with a personal access token:

```bash
cd edge/
python -m pip install -e .
cp config.example.yml config.yml   # edit for your environment
rosetta-watchdog -c config.yml --token ghp_YourTokenHere
```

Or set the token via environment variable instead of `--token`:
- **Mac/Linux:** `export ROSETTA_GITHUB_TOKEN="ghp_..."`
- **PowerShell:** `$env:ROSETTA_GITHUB_TOKEN = "ghp_..."`
- **CMD:** `set ROSETTA_GITHUB_TOKEN=ghp_...`

If your `config.yml` has an `auth.token_url` block, the watchdog ignores the
PAT and refreshes Worker-issued install tokens automatically using the value
of `ROSETTA_INSTALL_TICKET` instead.

## Parser Backends

| Backend | Requires | Metadata depth |
|---------|----------|---------------|
| **XradiaPy** (default on Xradia machines) | Zeiss Xradia Software Suite | Full per-projection axis positions, dates, geometry |
| **olefile** (fallback) | `python -m pip install olefile` | Machine settings, geometry, acquisition parameters |

Set `parser_backend` in `config.yml` to `"auto"`, `"xradiaPy"`, or `"olefile"`.

## Multi-machine Support

Add multiple entries under `watch_directories` — each tagged with a
`machine_name` that will appear in the pushed metadata.

## How It Works

1. Polls configured directories for new `.txrm` / `.pca` files.
2. Parses metadata using XradiaPy (preferred) or olefile (fallback) for `.txrm`;
   built-in parser for `.pca`.
3. Pushes a Rosetta-compatible JSON file to `data/<facility>/` in
   `johntrue15/Rosetta` (auth: Worker-issued App token or PAT fallback).
4. The existing `parse-and-aggregate.yml` workflow aggregates it into
   `metadata.json` and `metadata.csv`.

## Manual end-to-end test of the new install flow

Use this checklist whenever you change anything in `cloudflare/worker.js`,
`docs/setup-facility/`, `.github/workflows/facility-onboard.yml`, or the
`templates/facility-repo/` workflows.

1. **Request a facility** in the wizard with a throw-away name like
   `e2e-<date>` and one fake machine entry.
2. **Maintainer approval**: add the `facility-approved` label on the issue.
   - `facility-onboard.yml` should create `data/e2e-<date>/config.yml`.
   - `Request companion repo from Rosetta Upload Worker` step should report
     `ok=true` and the comment should link to the wizard.
3. **Wizard Step 4 device flow**: reload the wizard signed in as the
   requester; you should land directly on Step 4.
   - Click *Start device authorization*, approve at github.com/login/device.
   - `bootstrap-panel` should reveal a one-liner; `deploy-status-panel`
     should appear with "No deploy run yet".
4. **Run the one-liner** in a Windows VM / Mac / Linux box. Confirm:
   - `actions-runner` directory created.
   - Runner registers (visible at
     `https://github.com/johntrue15/rosetta-facility-<slug>/settings/actions/runners`).
   - `deploy-watchdog.yml` triggers and turns green.
   - Service `RosettaWatchdog` (Windows) or `rosetta-watchdog` (Linux/macOS)
     is running.
5. **Push a test file** into the watch directory (use
   `edge/test_data/example.pca`). The wizard's Step 5 should detect the new
   file in `data/<slug>/` within ~30s.
6. **Update path**: bump `edge/` SHA on `main`. Trigger
   `update-watchdog.yml` from `Actions` on the companion repo; confirm a
   new `deploy-watchdog.yml` run starts and completes.
7. **Auth rotation**: tail the watchdog log; you should see at least one
   "Refreshed GitHub App installation token" entry within an hour.
