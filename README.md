# Rosetta Parsing & Metadata Pipeline




https://github.com/user-attachments/assets/b51b08f8-fcc0-4525-b66f-c64906176d6c




A pipeline that transforms scan metadata files into structured JSON and CSV formats — upload, parse, and export with zero local setup.

## Getting Started

Head to the **[Rosetta Upload Page](https://johntrue15.github.io/Rosetta/docs)** to get started. The web app walks you through everything:

1. **Sign in** with GitHub (OAuth) — you must be a collaborator on this repo.
2. **Drag & drop** your metadata files (`.rtf`, `.pca`, `.xtekct`, `.log`, etc.).
3. **Done.** GitHub Actions automatically parses, aggregates, and exports your data.

All instructions, supported formats, and configuration details are available on the docs site:

> **📖 [https://johntrue15.github.io/Rosetta/docs](https://johntrue15.github.io/Rosetta/docs)**

## What This Repo Does

When you upload a scan metadata file through the web UI (or commit one directly to `data/`), the automated pipeline:

1. **Parses** the file into structured JSON → `data/parsed/`
2. **Aggregates** all parsed results into a single `data/metadata.json`
3. **Exports** a flat CSV at `data/metadata.csv`, with configurable columns (`standard_format.json`) and user attribution (`users.csv`)

Everything is handled by GitHub Actions — no local environment needed.

## Repository Layout

| Path | Purpose |
|------|---------|
| `data/` | Upload target; also holds parsed JSON, completed originals, and output files |
| `scripts/` | Python parsers and export scripts |
| `docs/` | GitHub Pages upload UI & auth callback |
| `standard_format.json` | CSV column mapping configuration |
| `users.csv` | Folder → user mapping for scan attribution |
| `.github/workflows/` | CI/CD pipelines for parsing, aggregation, and CSV export |

## Contributing

See the docs site for details on adding new parsers or customizing the output format:

> **[https://johntrue15.github.io/Rosetta/docs](https://johntrue15.github.io/Rosetta/docs)**

## License

[Add your license information here]
