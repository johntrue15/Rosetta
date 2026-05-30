# Developer install test (new GitHub account)

Use this to test **the install step only** — device OAuth + the download-and-run
installer — without signing into the wizard or having collaborator access on
Rosetta.

## Quick start

1. **Create and approve a throwaway facility** (once, as maintainer):
   - Run the normal wizard **without** `?dev=1`, or create an issue manually and
     add the `facility-approved` label.
   - Note the slug, e.g. `my-install-test` → needs
     `data/my-install-test/config.yml` on `main`.

2. **Open developer mode** (any browser, any GitHub account — no wizard login):

   ```
   https://johntrue15.github.io/Rosetta/docs/setup-facility/?dev=1&slug=my-install-test
   ```

3. Click **Check config.yml** → should show green checkmark.

4. Click **Go to Step 3 — test device install**.

5. Click **Start device authorization** → at `github.com/login/device` sign in
   with your **test account** and approve **Rosetta Upload**.

6. In the **Download & run** panel, set a watch folder, click **Download
   installer**, and run the single command it shows on the CT machine
   (no admin required; installs Python automatically on Windows).

7. Drop a `.pca`/`.txrm` into the watch folder, then use **Verify data
   uploads** — it checks the companion repo where data lands.

## URL parameters

| Param | Example | Effect |
|-------|---------|--------|
| `dev=1` | required | Shows developer panel, skips wizard login for the install step |
| `slug` | `my-install-test` | Pre-fills facility slug |
| `step=3` (or `step=4`) | with `slug` | Auto-jumps to the install step on load |

**Bookmark example:**

```
https://johntrue15.github.io/Rosetta/docs/setup-facility/?dev=1&slug=dev-install-test
```

## Testing with a second GitHub account

Device OAuth is **separate** from wizard sign-in (`gh_token` in localStorage).

- Wizard login (Step 1) = browser OAuth popup → used for facility issues / API.
- Install-step device flow = short code at `github.com/login/device` → used for
  Rosetta Upload App + companion repo + install ticket.

To simulate a new facility user:

1. Use an incognito window (or clear site data for GitHub Pages).
2. Open `?dev=1&slug=…` — do **not** click “Sign in”.
3. Complete device auth while logged into GitHub as your **other account**.

That account does **not** need to be a Rosetta collaborator.

## Prerequisites

- Cloudflare Worker deployed with device-flow endpoints.
- **Rosetta Upload** GitHub App has **Device flow** enabled.
- Target facility already approved (`config.yml` on `main`).

## Cleanup after a manual test

- Delete companion repo: `x-raymetadata/rosetta-facility-<slug>`
- Remove `data/<slug>/` on main if desired
- On the CT machine (download-and-run install): stop the running watchdog
  (Ctrl+C) and remove `%USERPROFILE%\rosetta-watchdog` (Windows) or
  `$HOME/rosetta-watchdog` (macOS/Linux)
- On the CT machine (Advanced runner install): stop `RosettaWatchdog` service
  and remove `C:\rosetta-runner`

Or re-run the automated E2E workflow which cleans up for you.
