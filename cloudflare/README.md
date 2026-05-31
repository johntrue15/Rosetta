# Rosetta Upload Cloudflare Worker

The Worker at `cloudflare/worker.js` backs two flows for the Rosetta facility
pipeline:

1. **Legacy browser OAuth** (`GET /`) used by the early Setup-Facility wizard
   for maintainer sign-in.
2. **Device-code self-service install** (`POST /device/*`,
   `/facility/create-companion-repo`, `/runner/registration-token`,
   `/watchdog/token`, `/deploy/status`) used by the wizard's Install step.
   The primary path is **download-and-run** (the wizard generates a script
   that installs the watchdog directly); the `bootstrap-*` scripts +
   `/deploy/status` back the **Advanced** self-hosted-runner path. No PATs
   touch the user.

## Routes

| Route                                | Purpose                                                                                          |
| ------------------------------------ | ------------------------------------------------------------------------------------------------ |
| `GET  /`                             | OAuth start / callback for the wizard's maintainer sign-in.                                       |
| `POST /device/init`                  | Start a GitHub device-code flow for the Rosetta Upload App.                                       |
| `POST /device/poll`                  | Poll for device-code completion. Returns `{access_token,...}` when approved.                      |
| `POST /facility/create-companion-repo` | Create + seed `rosetta-facility-<slug>` private repo. Auth: bearer device token OR onboard HMAC. |
| `POST /runner/registration-token`    | Mint a runner-registration token + install ticket for the bootstrap script.                       |
| `POST /watchdog/token`               | Trade install ticket for a 1-hour App installation token (used by the watchdog).                  |
| `POST /watchdog/heartbeat`           | Ingest a watchdog status heartbeat into KV (auth: install ticket). Returns pending control commands. |
| `POST /watchdog/version`             | Target version for the facility's channel (auth: install ticket). Drives self-update.             |
| `POST /facility/status`              | Single-facility status (auth: install ticket **or** org member). Powers the post-install dashboard. |
| `POST /facility/data`                | List the watchdog's uploads in the companion repo via a read-only App token (ticket or org).      |
| `GET  /fleet/status`                 | Aggregated fleet status for the dashboard (auth: bearer token of an active `FACILITY_OWNER` org member). |
| `POST /fleet/command`                | Queue a control command (`pause`/`resume`/`run-once`/`reload-config`/`update-now`/`restart`/`configure`). Org-gated. |
| `POST /fleet/revoke` / `unrevoke`    | Kill switch: revoke/restore an install ticket by `slug` (or `jti`). Org-gated.                     |
| `POST /fleet/set-channel`            | Set a facility's update channel (`stable`/`beta`/`pinned` + `pin_version`). Org-gated.            |
| `GET  /fleet/audit`                  | Recent security/control events for a facility. Org-gated.                                          |
| `POST /deploy/status` or `GET ?…`    | Proxy the latest `deploy-watchdog.yml` run for a facility (auth: install ticket).                 |
| `POST /workflow/dispatch-deploy`   | Trigger `deploy-watchdog.yml` on the companion repo (auth: install ticket or HMAC).                 |
| `POST /e2e/cleanup`                  | Delete companion repo, facility data dir, and facility issue (auth: HMAC).                        |
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
| `FACILITY_OWNER`           | Optional override, default `x-raymetadata` (org where companion repos live). GitHub Apps cannot create repos under a personal account, so this must be an org.                    |
| `ALERT_SLACK_WEBHOOK`      | Optional. Slack incoming-webhook URL for stale-facility alerts (fleet monitoring).        |

Equivalent main-repo secrets for `facility-onboard.yml`:

| Repo secret                  | Purpose                                                |
| ---------------------------- | ------------------------------------------------------ |
| `ROSETTA_WORKER_URL`         | Base URL of this Worker, e.g. `https://rosetta.jtrue15.workers.dev`. |
| `ROSETTA_ONBOARD_HMAC_KEY`   | Matches `ONBOARD_HMAC_KEY` on the Worker.              |

## Fleet monitoring (Phase 1)

The watchdog periodically POSTs a status heartbeat (version, host, processed/
error counts, watch-dir health) to `POST /watchdog/heartbeat`, authenticated by
the same install ticket it uses for data pushes. The Worker stores the latest
heartbeat per facility in a KV namespace, and the org dashboard at
`docs/fleet/` reads it back via `GET /fleet/status`.

**Enable it (one command, run once by the maintainer — not per install):**

```bash
npm run worker:setup      # node-only: no npm/npx/wrangler needed (uses the REST API)
# or, if you have wrangler:
npm run worker:kv-setup
```

`worker:setup` finds-or-creates the `FLEET` KV namespace, writes the binding
into `wrangler.toml`, and deploys the Worker **while preserving every existing
secret** (it re-sends non-secret bindings and inherits secrets via
`keep_bindings`, so `GITHUB_APP_PRIVATE_KEY` etc. are never touched). It also
sets the cron schedule. `npm run worker:inspect` prints the live bindings
(values redacted) to verify. Until KV is configured the heartbeat and fleet
endpoints **degrade gracefully** (return `ok` / empty) so the rest of the
Worker keeps working.

> This is a **one-time server-side step**. It is *not* part of the end-user
> install — the per-user one-line installer just runs the watchdog, which talks
> to the already-bound Worker. One binding serves the whole fleet.

<details><summary>Manual equivalent</summary>

```bash
npx wrangler kv namespace create FLEET
# copy the printed id into the [[kv_namespaces]] block in wrangler.toml, then:
npm run worker:deploy
```
</details>

- **Dashboard access** is gated to **active members of the `FACILITY_OWNER`
  org**. The dashboard runs device OAuth requesting the `read:org` scope, and
  `/fleet/status` verifies membership with the caller's own token — no extra
  GitHub App permission required.
- **Stale alerts**: a cron (`*/15 * * * *` in `wrangler.toml`) flags facilities
  silent for >15 min. Set the optional `ALERT_SLACK_WEBHOOK` secret to receive
  Slack notifications; otherwise stale facilities just surface in the dashboard.

## Remote control, updates & security (Phases 2–4)

All of the following build on the heartbeat/KV channel and require the `FLEET`
KV namespace (above). The dashboard exposes them as per-facility buttons.

- **Remote control** — `POST /fleet/command` queues a command; the watchdog
  picks it up on its next heartbeat and acks it (so it runs once). Supported:
  `pause`, `resume`, `run-once`, `reload-config`, `configure` (e.g.
  `{polling_interval_seconds}`), `update-now`, `restart`.
- **Remote updates** — facilities have a channel (`stable`/`beta`/`pinned`) set
  via `/fleet/set-channel`. The watchdog polls `/watchdog/version`; the Worker
  maps the channel to a **GitHub Release** on the main repo (stable = latest
  release, beta = latest prerelease, pinned = an exact tag) and returns the
  zip + a `sha256` if one is present in the release body
  (`sha256: <64-hex>`). The watchdog verifies the hash, `pip install`s, and
  re-execs. With no releases yet it tracks `STABLE_REF` (default `main`) and
  only updates on an explicit `update-now`.
- **Kill switch** — `/fleet/revoke` writes a KV tombstone; `verifyInstallTicket`
  rejects revoked tickets (by `jti` or `slug`) everywhere, instantly cutting a
  compromised machine off from tokens, heartbeats, and deploys.
- **Machine binding** — the watchdog sends a stable `machine_id` on token and
  heartbeat requests. The Worker records the first one per facility and flags
  mismatches in the dashboard. Set `ENFORCE_MACHINE_BINDING=1` to also *deny*
  token mints from a different machine (a leaked ticket becomes useless).
- **Audit log** — token first-seen, machine conflicts, revocations, channel
  changes, and queued commands are recorded per facility and viewable via
  `/fleet/audit`.

Optional Worker vars/secrets for these phases: `ENFORCE_MACHINE_BINDING`
(bind enforcement), `STABLE_REF` (branch to track when no releases exist).

### Two dashboards

- **Per-facility (operator)** — the setup wizard's Step 4 becomes a live
  dashboard for the watchdog you just installed: status, uploaded-file list,
  and Stop/Start/Scan-now/Update/Restart buttons. It is authorized by the
  **install ticket** the operator already holds, so it works even though the
  operator is not an org member and can't read the private companion repo
  directly (the Worker reads it with a scoped App token).
- **Fleet (org)** — `docs/fleet/` shows every facility and adds channel,
  revoke, and audit controls. Gated to `FACILITY_OWNER` org members.

## Scaling to ~100 facilities

The design is built for a fleet; the main thing to size is **Workers KV**.

- **Writes** — each watchdog writes one heartbeat per
  `monitoring.interval_seconds` (default **300 s**) plus one on activity. ~100
  idle facilities ≈ 100 × 288 ≈ **29k writes/day**. That's comfortable on the
  **Workers Paid** plan (millions of KV writes/month included) but exceeds the
  free tier's 1k/day — use Paid for a real fleet. Don't lower the interval to a
  few seconds across the fleet; command latency is bounded by it, and a
  facility picks up commands immediately whenever it processes a file.
- **Reads** — `/fleet/status` reads every facility's key per refresh and the
  per-facility dashboard reads one. Keep the dashboard's auto-refresh modest
  (30 s fleet / 15 s single) and don't leave many dashboards open.
- **Cron** — stale detection lists all keys every 15 min (~100 reads/run).
- **Beyond ~1,000 facilities**, move the store from KV to **D1** (SQLite) for
  indexed queries and higher write throughput; the endpoint shapes stay the same.

### Ready-for-100 checklist

- [ ] `FACILITY_OWNER` org has the app installed; `npm run worker:kv-setup` run.
- [ ] Workers **Paid** plan enabled (KV quotas).
- [ ] `ENFORCE_MACHINE_BINDING=1` if you want leaked-ticket protection.
- [ ] Use update **channels** (`beta` on a couple of canaries before `stable`).
- [ ] Each facility is isolated: its own approved allow-list entry, its own
      private companion repo, and only scoped, short-lived tokens leave the Worker.
- [ ] `ALERT_SLACK_WEBHOOK` set so stale facilities page someone.

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

## Local credentials and deploy (no Cloudflare dashboard)

All secrets stay in **gitignored local files**. Copy the examples once, fill in
values, then deploy from the repo root.

### 1. Cloudflare API credentials (for `wrangler deploy`)

```powershell
# Windows (PowerShell, from repo root)
copy cloudflare\credentials.example.env cloudflare\credentials.env
# Edit cloudflare\credentials.env — set CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID
```

```bash
# macOS/Linux
cp cloudflare/credentials.example.env cloudflare/credentials.env
```

Create a token at https://dash.cloudflare.com/profile/api-tokens  
Use template **Edit Cloudflare Workers** (Account + Workers Scripts: Edit).

**Account ID:** Cloudflare dashboard → any zone/workers overview → right sidebar.

### 2. Worker secrets (GitHub App, OAuth, HMAC keys)

```powershell
copy .dev.vars.example .dev.vars
# Edit .dev.vars — GITHUB_CLIENT_ID, GITHUB_APP_PRIVATE_KEY, etc.
```

Upload to Cloudflare (once, or after changing secrets):

```powershell
npm install
npm run worker:secrets
```

### 3. Deploy

```powershell
npm run worker:deploy
# or directly:
.\cloudflare\deploy.ps1
```

```bash
npm run worker:deploy
# or: bash cloudflare/deploy.sh deploy
```

### 4. Local dev (optional)

```powershell
npm run worker:dev
# Worker at http://127.0.0.1:8787 — uses .dev.vars automatically
```

### Alternative: `wrangler login` (interactive, no API token file)

```powershell
npx wrangler login
npx wrangler deploy
```

Still need `wrangler secret bulk .dev.vars` for GitHub secrets on first setup.

### File reference

| File | Gitignored | Purpose |
|------|------------|---------|
| `cloudflare/credentials.env` | yes | `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID` |
| `.dev.vars` | yes | Worker runtime secrets (GitHub App, OAuth, HMAC) |
| `cloudflare/credentials.example.env` | no | Template for Cloudflare API |
| `.dev.vars.example` | no | Template for Worker secrets |

---

## Local development / deploy (legacy one-liners)

## Drift between Worker templates and `templates/facility-repo/`

The Worker keeps inline copies of the per-facility workflow YAML and bootstrap
scripts (so seeding a new companion repo is a single POST). The same files
are also committed under `templates/facility-repo/` and `cloudflare/worker.js`
inline `*_Yaml()` / `*_Bootstrap()` helpers for code review. If you change one,
update the other and bump the deploy.
