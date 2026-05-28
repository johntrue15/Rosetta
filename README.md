# Rosetta

> CT scanner metadata pipeline — upload, parse, and export with zero local setup.

**[Upload Page](https://johntrue15.github.io/Rosetta/docs)** · **[Setup Facility](https://johntrue15.github.io/Rosetta/docs/setup-facility/)**

---

https://github.com/user-attachments/assets/b51b08f8-fcc0-4525-b66f-c64906176d6c

---



https://github.com/user-attachments/assets/62d49389-fbd3-42f5-875f-0c6faad48917




## How It Works

### Manual upload (web UI)
1. **Sign in** with GitHub — collaborator access is required to push files via the upload page.
2. **Upload** metadata files (`.rtf`, `.pca`, `.xtekct`, `.log`, `.txrm`) via drag & drop or remote URL.
3. **GitHub Actions** parses each file into JSON, aggregates results into `data/metadata.json`, and exports a flat CSV at `data/metadata.csv`.

### Automated facility install (recommended for CT scanners)
Use the **[Setup Facility](https://johntrue15.github.io/Rosetta/docs/setup-facility/)** wizard — **no collaborator access** on the main repo required:

1. **Request** a facility via a GitHub issue (from the wizard or issue template).
2. **Maintainer approves** by adding the `facility-approved` label.
3. **Device-code OAuth** authorizes the **Rosetta Upload** GitHub App (short code at `github.com/login/device` — no PAT).
4. **Bootstrap one-liner** registers a self-hosted runner on a private `rosetta-facility-<slug>` companion repo and deploys the [Edge Watchdog](edge/) as a service.

## Repository Layout

| Path | Purpose |
|------|---------|
| `data/` | Upload target; parsed JSON, completed originals, and output files |
| `scripts/` | Python parsers and export scripts |
| `edge/` | Rosetta Edge Watchdog — local file watcher that pushes metadata to GitHub |
| `docs/` | GitHub Pages upload UI, auth callback, and facility setup wizard |
| `cloudflare/` | Rosetta Upload Cloudflare Worker (OAuth, device flow, App token issuance) |
| `templates/facility-repo/` | Files seeded into each `rosetta-facility-<slug>` companion repo |
| `.github/scripts/e2e/` | Windows E2E CI — **[Dell setup guide](.github/scripts/e2e/DELL_SETUP.md)** for Cursor agents |
| `standard_format.json` | CSV column mapping configuration |
| `users.csv` | Folder-to-user mapping for scan attribution |
| `.github/workflows/` | CI/CD pipelines for parsing, aggregation, CSV export, facility onboarding |
