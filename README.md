# Rosetta Parsing & Metadata Pipeline




https://github.com/user-attachments/assets/71d9d673-6079-481e-a734-627c618beeae



A comprehensive pipeline that transforms heterogeneous scan metadata files into clean, structured JSON and CSV formats with automated processing and user attribution.

## Overview

This pipeline processes various metadata file formats from X-ray and CT scanning equipment, extracting structured information and maintaining a cumulative database of all processed files.

### Key Features

- **Multi-format parsing**: Supports `.rtf`, `.pca`, `.xtekct` files with extensible architecture
- **Automated file management**: Moves processed files to organized directories
- **Cumulative aggregation**: Maintains a single, de-duplicated metadata database
- **User attribution**: Maps scan data to users based on configurable directory patterns
- **CI/CD integration**: Automated processing via GitHub Actions

## How It Works

### 1. File Parsing
- Parses source metadata files into structured JSON format
- Supported formats: `.rtf`, `.pca`, `.xtekct` (with generic fallback for others)
- Parsed JSON saved to `data/parsed/<original-name>.<ext>.json`
- Successfully parsed originals moved to `data/completed/`

### 2. Data Aggregation
- `scripts/aggregate_json.py` collects all parsed JSON files
- Creates cumulative `data/metadata.json` with automatic de-duplication
- Maintains historical record of all processed files

### 3. CSV Export
- `scripts/metadata_to_csv.py` flattens JSON data into `data/metadata.csv`
- Adds "X-ray User" column based on directory-to-user mapping
- Provides tabular format for analysis and reporting

## Repository Structure

```
data/
├── parsed/           # Auto-created: all parsed JSON files
├── completed/        # Auto-created: original files after processing
├── metadata.json     # Cumulative JSON database (de-duplicated)
├── metadata.csv      # Flat CSV export from metadata.json
└── users.csv         # Optional user mapping (Folder → Email)

scripts/
├── parse_any.py      # Main parsing dispatcher
├── rtf_to_json.py    # RTF format parser
├── pca_to_json.py    # PCA format parser
├── xtekct_to_json.py # XTEKCT format parser
├── aggregate_json.py # JSON aggregation script
└── metadata_to_csv.py # CSV export script

.github/workflows/
├── parse-and-aggregate.yml # Auto-parsing and aggregation
└── metadata-to-csv.yml     # CSV generation workflow
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
