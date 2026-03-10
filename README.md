# Rosetta Parsing & Metadata Pipeline




https://github.com/user-attachments/assets/b51b08f8-fcc0-4525-b66f-c64906176d6c





A comprehensive pipeline that transforms heterogeneous scan metadata files into clean, structured JSON and CSV formats with automated processing and user attribution.

## Quick Start – Drag & Drop Upload

The easiest way to add metadata files is through the **[Rosetta Upload Page](https://johntrue15.github.io/Rosetta/)** (GitHub Pages):

1. **Open** the [upload page](https://johntrue15.github.io/Rosetta/).
2. **Sign in** with a GitHub Personal Access Token that has `repo` scope.  
   - You must be a **collaborator** on this repository.
   - Create a token at [github.com/settings/tokens/new](https://github.com/settings/tokens/new).
3. **Drag & drop** your `.rtf`, `.pca`, `.xtekct`, `.log` (Bruker SkyScan), or other metadata files onto the upload area (or click to browse).
4. Files are committed directly to the `data/` directory via the GitHub API.
5. **GitHub Actions** automatically parses, aggregates, and exports your data — no local setup required.

> **Note:** Your token is stored only in the browser tab's session and is never sent to any third-party service.

### Alternative: Manual Drag & Drop via GitHub.com

You can also upload files directly through the GitHub web interface:

1. Navigate to the [`data/`](https://github.com/johntrue15/Rosetta/tree/main/data) directory on GitHub.
2. Click **Add file → Upload files**.
3. Drag and drop your metadata files and commit.
4. The CI/CD pipeline will process them automatically.

## Overview

This pipeline processes various metadata file formats from X-ray and CT scanning equipment, extracting structured information and maintaining a cumulative database of all processed files.

### Key Features

- **Multi-format parsing**: Supports `.rtf`, `.pca`, `.xtekct`, `.log` (Bruker SkyScan) files with extensible architecture
- **Automated file management**: Moves processed files to organized directories
- **Cumulative aggregation**: Maintains a single, de-duplicated metadata database
- **Configurable CSV output**: `standard_format.json` controls column names, order, and inclusion
- **User attribution**: Maps scan data to users based on configurable directory patterns
- **Upload tracking**: Records which GitHub user uploaded each file via OAuth identity
- **CI/CD integration**: Automated processing via GitHub Actions

## How It Works

### 1. File Parsing
- Parses source metadata files into structured JSON format
- Supported formats: `.rtf`, `.pca`, `.xtekct`, `.log` (Bruker SkyScan) (with generic fallback for others)
- Parsed JSON saved to `data/parsed/<original-name>.<ext>.json`
- Successfully parsed originals moved to `data/completed/`

### 2. Data Aggregation
- `scripts/aggregate_json.py` collects all parsed JSON files
- Creates cumulative `data/metadata.json` with automatic de-duplication
- Maintains historical record of all processed files

### 3. CSV Export
- `scripts/metadata_to_csv.py` flattens JSON data into `data/metadata.csv`
- Reads `standard_format.json` to control column names, order, and which fields to include
- Adds "X-ray User" column based on directory-to-user mapping (`users.csv`)
- Adds "Uploaded By" column from the GitHub identity that uploaded the file
- Falls back to sensible defaults if `standard_format.json` is not present

## Repository Structure

```
data/
├── parsed/           # Auto-created: all parsed JSON files
├── completed/        # Auto-created: original files after processing
├── metadata.json     # Cumulative JSON database (de-duplicated)
├── metadata.csv      # Flat CSV export from metadata.json
└── users.csv         # Optional user mapping (Folder → Email)

standard_format.json  # CSV column mapping config (edit to customize output)

scripts/
├── parse_any.py      # Main parsing dispatcher (supports --uploaded-by)
├── rtf_to_json.py    # RTF format parser
├── pca_to_json.py    # PCA format parser
├── xtekct_to_json.py # XTEKCT format parser
├── skyscan_to_json.py # Bruker SkyScan .log parser
├── aggregate_json.py # JSON aggregation script
└── metadata_to_csv.py # CSV export (reads standard_format.json)

.github/workflows/
├── parse-and-aggregate.yml # Auto-parsing and aggregation
└── metadata-to-csv.yml     # CSV generation workflow

docs/
└── index.html        # GitHub Pages drag-and-drop upload UI
```

## User Mapping Configuration

The pipeline can automatically attribute scans to users based on directory paths using `data/users.csv`:

### Format
```csv
Folder,User name,Email
FICS,Lab A,fics-lab@example.org
FA no band filter with aluminum,Stanley,stanley@example.org
S:\CT_DATA\FICS\FA no band filter with aluminum,Team X,xteam@example.org
```

### Matching Strategy (most specific wins)
1. Exact match: Any path component equals `Folder` (case/space-insensitive)
2. Substring match: `Folder` found within any full candidate path

**Note**: Headers are optional, and both comma and tab delimiters are supported.

## CSV Output Configuration (`standard_format.json`)

The `standard_format.json` file in the repo root controls the CSV output format. Edit it to:
- **Rename columns**: Change `"name"` to set the display header for any field
- **Reorder columns**: Move entries up or down in the `"columns"` array
- **Hide columns**: Remove an entry, or set `"include": false`
- **Show everything**: Set `"include_unmapped": true` to include fields not explicitly listed

### Example

```json
{
  "version": 1,
  "include_unmapped": true,
  "columns": [
    {"source": "file_name",          "name": "File Name"},
    {"source": "uploaded_by",        "name": "Uploaded By"},
    {"source": "xray_tube_voltage",  "name": "Voltage (kV)"},
    {"source": "xray_tube_current",  "name": "Current (uA)"},
    {"source": "ct_voxel_size_um",   "name": "Voxel Size (um)"},
    {"source": "sha256",             "name": "Hash", "include": false},
    {"source": "X-ray User",         "name": "X-ray User"}
  ]
}
```

Each entry maps an internal field (`source`) to a display name (`name`). The CSV columns appear in the exact order listed. When `include_unmapped` is `true`, any fields from the metadata that aren't explicitly listed are appended at the end. If the file is missing, the pipeline falls back to the default column order with original field names.

## Upload Tracking

When files are uploaded through the [Rosetta Upload Page](https://johntrue15.github.io/Rosetta/), the GitHub username of the uploader is automatically recorded:

1. The web UI embeds the uploader's GitHub login in the commit message (e.g., `Upload file.pca via Rosetta [uploader:johntrue15]`)
2. The CI workflow extracts the uploader identity from the commit history
3. The parsed JSON receives an `uploaded_by` field
4. The CSV output shows this as the "Uploaded By" column (configurable via `standard_format.json`)

This means you can always trace **who ran the scan** (from `users.csv` → "X-ray User") and **who uploaded the file** (from OAuth → "Uploaded By").

## Local Setup & Usage

### Prerequisites
- Python 3.11 or higher
- Required packages: `striprtf`, `pandas`

### Installation
```bash
# Install dependencies
python -m pip install --upgrade pip
pip install striprtf pandas
```

### Usage Examples

#### Parse a single file
```bash
python scripts/parse_any.py data/yourfile.pca \
  -o data/parsed \
  --completed-dir data/completed \
  --pretty

# With uploader tracking:
python scripts/parse_any.py data/yourfile.pca \
  -o data/parsed \
  --completed-dir data/completed \
  --pretty \
  --uploaded-by your_github_username
```

#### Aggregate all JSON files
```bash
python scripts/aggregate_json.py
```

#### Generate CSV with user mapping
```bash
# Enable verbose matching logs (optional)
export LOG_MATCHES=1
python scripts/metadata_to_csv.py
```

## Special Handling: PCA Files

For Phoenix/Waygate `.pca` files, the parser extracts calibration paths from the `[CalibImages]` section:
- `MGainImg`, `OffsetImg`, `GainImg`, `DefPixelImg`

The system sets:
- `calib_images.calib_folder_path`: Folder of the first valid calibration path
- `file_path`: Set to calibration folder path for reliable downstream matching

Example: `S:\CT_DATA\FICS\FA no band filter with aluminum`

## Special Handling: SkyScan Files

For Bruker SkyScan `.log` reconstruction files, the parser extracts metadata from all four INI sections:
- **`[System]`**: Scanner model, source type, camera pixel size
- **`[Acquisition]`**: Voltage, current, filter, voxel size, exposure, frame averaging, distances, scan duration
- **`[Reconstruction]`**: NRecon/InstaRecon parameters, ring artifact correction, beam hardening, filter type
- **`[File name convention]`**: Filename prefix information

Key field mappings:
- `Image Pixel Size (um)` → `ct_voxel_size_um` (already in µm, no conversion needed)
- `Object to Source (mm)` / `Camera to Source (mm)` → source distances and geometric magnification
- `Scan duration` (e.g. `0h:18m:3s`) → `scan_time` in seconds
- `Frame Averaging` (e.g. `ON (2)`) → `detector_averaging` extracts the count
- Reconstruction parameters are preserved in a nested `reconstruction` object

## Automated Workflows

### 1. Parse & Aggregate Workflow
**Trigger**: Changes to files under `data/**`

**Actions**:
- Parses supported metadata files
- Writes JSON to `data/parsed/`
- Moves originals to `data/completed/`
- Aggregates to `data/metadata.json`
- Commits results automatically

### 2. Metadata → CSV Workflow
**Trigger**: Changes to `data/metadata.json` or `data/users.csv`

**Actions**:
- Generates `data/metadata.csv` from JSON data
- Applies user mapping if available
- Commits updated CSV

Both workflows include `[skip ci]` tags to prevent infinite loops.

## Troubleshooting

### Common Issues

**Missing X-ray User attribution**
- Ensure `data/users.csv` exists and is properly formatted
- Set `LOG_MATCHES=1` environment variable for detailed matching diagnostics
- Check that folder paths in users.csv match actual scan directory structures

**Workflow errors**
- Verify you're using only `paths:` (not `paths-ignore:`) in workflow configurations
- Check that required permissions (`contents: write`) are set

**Aggregator directory errors**
- The aggregator automatically creates parent directories as needed
- Default output is `data/metadata.json`

### Debugging Tips

1. **Enable verbose logging**: Set `LOG_MATCHES=1` when running CSV generation
2. **Check file permissions**: Ensure write access to `data/` directory
3. **Validate CSV format**: Verify `users.csv` has proper headers and delimiter format

## Contributing

When adding new file format parsers:
1. Create a new parser script in `scripts/` following existing patterns
2. Register the extension in `parse_any.py`
3. Update this README with the new supported format
4. Test with sample files to ensure proper JSON structure

## License

[Add your license information here]
