# Developer install test (new GitHub account)

Use this to test **Step 4 only** — device OAuth, bootstrap one-liner, deploy
status — without signing into the wizard or having collaborator access on
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

4. Click **Go to Step 4 — test device install**.

5. Click **Start device authorization** → at `github.com/login/device` sign in
   with your **test account** and approve **Rosetta Upload**.

6. Copy the **Windows PowerShell** one-liner → paste on the CT machine / Dell
   (Administrator PowerShell).

7. Watch **Deploy progress** → when green, use **Verify data uploads** (works
   without wizard sign-in for public repo reads).

## URL parameters

| Param | Example | Effect |
|-------|---------|--------|
| `dev=1` | required | Shows developer panel, skips wizard login for Step 4 |
| `slug` | `my-install-test` | Pre-fills facility slug |
| `step=4` | with `slug` | Auto-jumps to Step 4 on load |

**Bookmark example:**

```
https://johntrue15.github.io/Rosetta/docs/setup-facility/?dev=1&slug=dev-install-test
```

## Testing with a second GitHub account

Device OAuth is **separate** from wizard sign-in (`gh_token` in localStorage).

- Wizard login (Step 1) = browser OAuth popup → used for facility issues / API.
- Step 4 device flow = short code at `github.com/login/device` → used for
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

- Delete companion repo: `johntrue15/rosetta-facility-<slug>`
- Remove `data/<slug>/` on main if desired
- On the CT machine: stop `RosettaWatchdog` service and remove `C:\rosetta-runner`

Or re-run the automated E2E workflow which cleans up for you.
