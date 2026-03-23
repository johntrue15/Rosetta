# Rosetta Edge Watchdog

Standalone service that monitors Xradia CT scanner output directories for new
`.txrm` files, extracts metadata, and pushes it to the Rosetta GitHub
repository for aggregation.

## Quick Start

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

1. Polls configured directories for new `.txrm` files
2. Parses metadata using XradiaPy (preferred) or olefile (fallback)
3. Pushes a Rosetta-compatible JSON file to `data/` in the GitHub repo
4. The existing `parse-and-aggregate.yml` workflow aggregates it into
   `metadata.json` and `metadata.csv`
