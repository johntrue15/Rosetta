# Rosetta Edge Watchdog

Standalone service that monitors Xradia / Phoenix CT scanner output
directories for new `.txrm` / `.pca` files, extracts metadata, and pushes it
to the Rosetta GitHub repository for aggregation.

## Recommended install — Setup Facility wizard (download & run)

Go to **<https://johntrue15.github.io/Rosetta/docs/setup-facility/>** and
follow the wizard. After approval, the Install step will:

1. Run a device-code flow against the **Rosetta Upload** GitHub App
   (you type a short code at `github.com/login/device` — no token to copy).
2. Auto-create your private `x-raymetadata/rosetta-facility-<slug>` companion
   repo, where this facility's scan metadata is stored.
3. Generate a **download-and-run installer** (`.ps1` for Windows, `.sh` for
   macOS/Linux). Download it and run a single command on the CT machine. The
   installer:
   - installs **Python automatically** if missing (Windows, per-user, no admin),
   - downloads the watchdog from a repo **ZIP** (no Git required),
   - `pip install`s the watchdog and writes a `config.yml`, and
   - starts monitoring your scan folder.

The watchdog never holds a PAT — it refreshes a 1-hour GitHub App installation
token from the Cloudflare Worker (using the embedded install ticket) before
each push.

> **Advanced (auto-start service):** the wizard also offers a self-hosted
> GitHub Actions runner one-liner that installs the watchdog as a background
> service via `deploy-watchdog.yml`. This requires an **administrator**
> terminal and is mainly useful for unattended machines. Most users should
> prefer the download-and-run installer above.

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
3. Pushes a Rosetta-compatible JSON file to `data/<slug>/` in the facility's
   private companion repo `x-raymetadata/rosetta-facility-<slug>` (auth:
   Worker-issued, repo-scoped App token; PAT fallback for legacy installs that
   target `johntrue15/Rosetta`).
4. Aggregation workflows process it into `metadata.json` / `metadata.csv`.

## Manual end-to-end test of the new install flow

For automated regression on the Dell Windows machine, see
[`.github/scripts/e2e/README.md`](../.github/scripts/e2e/README.md) and the
`watchdog-windows-e2e.yml` workflow (enable with repo variable
`ROSETTA_E2E_ENABLED=true`).

Manual checklist (when changing install components):
`docs/setup-facility/`, `.github/workflows/facility-onboard.yml`, or the
`templates/facility-repo/` workflows.

1. **Request a facility** in the wizard with a throw-away name like
   `e2e-<date>` and one machine entry (watch path can be a local test folder).
2. **Maintainer approval**: add the `facility-approved` label on the issue.
   - `facility-onboard.yml` should create `data/e2e-<date>/config.yml`.
   - `Request companion repo from Rosetta Upload Worker` step should report
     `ok=true` and the comment should link to the wizard.
3. **Wizard Install step (device flow)**: reload the wizard signed in as the
   requester; you should land directly on the Install step.
   - Click *Start device authorization*, approve at github.com/login/device.
   - The **Download & run** panel should appear with a watch-folder field and
     a *Download installer* button.
4. **Download and run the installer** on a Windows / Mac / Linux box.
   Confirm in the console:
   - On Windows without Python: it auto-installs Python, then continues.
   - It downloads the repo ZIP, `pip install`s the watchdog, writes
     `config.yml`, and prints the startup banner with `[OK] <watch folder>`.
5. **Drop a test file** (`edge/test_data/example.pca`) into the watch folder.
   Within ~30s the log should show it parsing and pushing
   `<name>.pca.json` to `data/<slug>/` in the companion repo. The wizard's
   verify step should detect it in the companion repo.
6. **Auth rotation**: tail the watchdog log; you should see at least one
   "Refreshed GitHub App installation token" entry within an hour.

> The **Advanced** self-hosted-runner path (`bootstrap-windows.ps1` →
> `deploy-watchdog.yml` → `RosettaWatchdog` service) is exercised by the
> automated Dell E2E (`watchdog-windows-e2e.yml`); see
> [`.github/scripts/e2e/README.md`](../.github/scripts/e2e/README.md).
