# Rosetta

> CT scanner metadata pipeline — upload, parse, and export with zero local setup.

**[Upload Page](https://johntrue15.github.io/Rosetta/docs)** · **[Setup Facility](https://johntrue15.github.io/Rosetta/docs/setup-facility/)**

---

https://github.com/user-attachments/assets/b51b08f8-fcc0-4525-b66f-c64906176d6c

---

## How It Works

1. **Sign in** with GitHub — you must be a collaborator on this repo.
2. **Upload** metadata files (`.rtf`, `.pca`, `.xtekct`, `.log`, `.txrm`) via drag & drop or remote URL.
3. **GitHub Actions** parses each file into JSON, aggregates results into `data/metadata.json`, and exports a flat CSV at `data/metadata.csv`.

For automated uploads from a CT scanner, use the **[Setup Facility](https://johntrue15.github.io/Rosetta/docs/setup-facility/)** wizard to onboard your machine and install the [Edge Watchdog](edge/).

## Repository Layout

| Path | Purpose |
|------|---------|
| `data/` | Upload target; parsed JSON, completed originals, and output files |
| `scripts/` | Python parsers and export scripts |
| `edge/` | Rosetta Edge Watchdog — local file watcher that pushes metadata to GitHub |
| `docs/` | GitHub Pages upload UI, auth callback, and facility setup wizard |
| `standard_format.json` | CSV column mapping configuration |
| `users.csv` | Folder-to-user mapping for scan attribution |
| `.github/workflows/` | CI/CD pipelines for parsing, aggregation, and CSV export |
