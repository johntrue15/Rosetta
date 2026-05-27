# Rosetta Upload Cloudflare Worker

The Worker at `cloudflare/worker.js` backs two flows for the Rosetta facility
pipeline:

1. **Legacy browser OAuth** (`GET /`) used by the early Setup-Facility wizard
   for maintainer sign-in.
2. **Device-code self-service install** (`POST /device/*`,
   `/facility/create-companion-repo`, `/runner/registration-token`,
   `/watchdog/token`, `/deploy/status`) used by the new wizard Step 4 +
   per-facility runner bootstrap. No PATs touch the user.

## Routes

| Route                                | Purpose                                                                                          |
| ------------------------------------ | ------------------------------------------------------------------------------------------------ |
| `GET  /`                             | OAuth start / callback for the wizard's maintainer sign-in.                                       |
| `POST /device/init`                  | Start a GitHub device-code flow for the Rosetta Upload App.                                       |
| `POST /device/poll`                  | Poll for device-code completion. Returns `{access_token,...}` when approved.                      |
| `POST /facility/create-companion-repo` | Create + seed `rosetta-facility-<slug>` private repo. Auth: bearer device token OR onboard HMAC. |
| `POST /runner/registration-token`    | Mint a runner-registration token + install ticket for the bootstrap script.                       |
| `POST /watchdog/token`               | Trade install ticket for a 1-hour App installation token (used by the watchdog).                  |
| `POST /deploy/status` or `GET ?…`    | Proxy the latest `deploy-watchdog.yml` run for a facility (auth: install ticket).                 |
| `GET  /bootstrap-windows.ps1`        | PowerShell installer served as plain text.                                                        |
| `GET  /bootstrap-unix.sh`            | bash installer served as plain text.                                                              |

## Required environment / secrets

Set these via `wrangler secret put` (don't commit them to `wrangler.toml`).

| Name                       | Purpose                                                                                  |
| -------------------------- | ---------------------------------------------------------------------------------------- |
| `GITHUB_CLIENT_ID`         | OAuth client id of the **Rosetta Upload** GitHub App.                                    |
| `GITHUB_CLIENT_SECRET`     | OAuth client secret (legacy browser OAuth only).                                          |
| `GITHUB_REDIRECT_URI`      | Public Worker URL, e.g. `https://rosetta.jtrue15.workers.dev` (used for OAuth callback). |
| `ALLOWED_ORIGIN`           | `https://johntrue15.github.io` (CORS allow-list).                                         |
| `GITHUB_APP_ID`            | Numeric App id of Rosetta Upload.                                                         |
| `GITHUB_APP_PRIVATE_KEY`   | PEM-encoded RSA private key for the App (multi-line).                                     |
| `INSTALL_TICKET_KEY`       | Random 32+ byte secret used to HMAC install tickets handed to the bootstrap + watchdog. |
| `ONBOARD_HMAC_KEY`         | Shared with `facility-onboard.yml` (`secrets.ROSETTA_ONBOARD_HMAC_KEY`).                  |
| `MAIN_REPO`                | Optional override, default `johntrue15/Rosetta`.                                         |
| `FACILITY_OWNER`           | Optional override, default `johntrue15` (where companion repos live).                    |

Equivalent main-repo secrets for `facility-onboard.yml`:

| Repo secret                  | Purpose                                                |
| ---------------------------- | ------------------------------------------------------ |
| `ROSETTA_WORKER_URL`         | Base URL of this Worker, e.g. `https://rosetta.jtrue15.workers.dev`. |
| `ROSETTA_ONBOARD_HMAC_KEY`   | Matches `ONBOARD_HMAC_KEY` on the Worker.              |

## GitHub App "Rosetta Upload" — required permissions

In the App settings page (`https://github.com/settings/apps/rosetta-upload`):

1. **Identifying and authorizing users → Device flow** — must be **enabled**.
2. **Repository permissions**:
   - `Administration`: **Read & write** (runner registration tokens, create per-facility repos).
   - `Contents`: **Read & write** (push parsed JSON to `johntrue15/Rosetta`, seed companion repos).
   - `Metadata`: **Read** (default).
   - `Actions`: **Read & write** (workflow_dispatch + run lookup).
3. **Account / Organization permissions** (whichever account owns the
   companion repos, default `johntrue15`):
   - `Administration`: **Read & write** (so the App can create new repos via `POST /user/repos`).
4. **Install** the App on the account/org named in `FACILITY_OWNER` and on
   the main `johntrue15/Rosetta` repository.

## Local development / deploy

```bash
# Install wrangler if you haven't
npm install -g wrangler

# Set secrets (interactive; never commit values)
cd cloudflare
wrangler secret put GITHUB_APP_ID
wrangler secret put GITHUB_APP_PRIVATE_KEY
wrangler secret put INSTALL_TICKET_KEY
wrangler secret put ONBOARD_HMAC_KEY
# (and the existing GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET, GITHUB_REDIRECT_URI)

# Deploy
wrangler deploy
```

The Worker config in `wrangler.toml` only pins `name`, `main`, and the
public `ALLOWED_ORIGIN` var.

## Drift between Worker templates and `templates/facility-repo/`

The Worker keeps inline copies of the per-facility workflow YAML and bootstrap
scripts (so seeding a new companion repo is a single POST). The same files
are also committed under `templates/facility-repo/` and `cloudflare/worker.js`
inline `*_Yaml()` / `*_Bootstrap()` helpers for code review. If you change one,
update the other and bump the deploy.
