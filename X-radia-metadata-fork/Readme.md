# X-radia Metadata Extractor

A comprehensive Python tool for extracting and processing metadata from X-radia TXRM files. This tool provides automated metadata extraction, configuration file generation, CSV export, and continuous directory monitoring.

## Features

- **Automated Metadata Extraction**: Extract comprehensive metadata from TXRM files
- **Multiple Output Formats**: Generate text files, configuration files, and cumulative CSV
- **Watch Mode**: Automatically monitor directories for new TXRM files
- **Interactive & Batch Processing**: Choose your workflow preference
- **Docker Support**: Run in a container - no Python installation required
- **PyCharm Integration**: Pre-configured run configurations for easy development
- **System Detection**: Auto-detect Python and XradiaPy installation
- **Contact Management**: Track metadata attribution with contacts.csv

---

## Quick Start

### Option 1: One-Click Start (Recommended)

**Windows:** Double-click `run.bat`

**Mac/Linux:** Run `./run.sh`

The smart launcher shows what's installed and guides you through setup.

### Option 2: Docker (No Python Required)

```bash
# Windows
docker-run.bat C:\path\to\txrm\files

# Mac/Linux
./docker-run.sh /path/to/txrm/files
```

See [DOCKER.md](DOCKER.md) for full Docker documentation.

### Option 3: Manual Setup

1. **Download** the repository as ZIP from GitHub
2. **Extract** to your preferred location
3. **Run the smart launcher**:
   ```bash
   python start.py
   ```

### For Developers (Git Clone)

```bash
# Clone the repository
git clone https://github.com/yourusername/X-radia-metadata.git
cd X-radia-metadata

# Run smart launcher (checks system & guides setup)
python start.py

# Or run system check directly
python system_check.py
```

---

## Prerequisites

### Option A: Docker (Easiest)

| Requirement | Details |
|-------------|---------|
| **Docker** | [Docker Desktop](https://www.docker.com/get-started) |
| **XradiaPy** | Mount from host if available |

### Option B: Local Python

| Requirement | Details |
|-------------|---------|
| **Python** | 2.7.x (required for XradiaPy) |
| **XradiaPy** | From Zeiss Xradia Software Suite |
| **IDE** | PyCharm (recommended) |
| **OS** | Windows, macOS, or Linux |

---

## Installation

Choose your preferred method:

| Method | Best For | Guide |
|--------|----------|-------|
| **Docker** | Quick setup, no Python needed | [DOCKER.md](DOCKER.md) |
| **One-Click** | Windows/Mac users | Run `run.bat` or `./run.sh` |
| **Manual** | Full control | [INSTALL.md](INSTALL.md) |

### Quick Setup (Local Python)

```bash
# Run the smart launcher - it checks everything and guides you
python start.py
```

The launcher will:
- Show what's installed (with versions)
- Highlight what's missing
- Offer to install dependencies
- Start the app when ready

---

## Project Structure

```
X-radia-metadata/
├── new_enhanced_interactive/     # Main package
│   ├── config/                   # Configuration modules
│   │   ├── watch_config.py       # Watch mode settings
│   │   ├── user_config.py        # User preferences
│   │   └── txrm_config_converter.py
│   ├── metadata/                 # Metadata extraction
│   │   └── metadata_extractor.py # Core extractor
│   ├── processors/               # File processing
│   │   └── txrm_processor.py     # TXRM file processor
│   ├── utils/                    # Utilities
│   │   ├── file_utils.py         # File operations
│   │   ├── file_watcher.py       # Directory monitoring
│   │   ├── github_utils.py       # GitHub integration
│   │   └── validation_utils.py   # File validation
│   └── main.py                   # Main entry point
├── scripts/                      # Legacy standalone scripts
├── contacts.csv                  # Contact information
├── requirements.txt              # Python dependencies
├── setup.py                      # Package installation
├── system_check.py               # System diagnostics
├── setup_wizard.py               # Interactive setup
├── INSTALL.md                    # Installation guide
└── Readme.md                     # This file
```

---

## Usage

### Interactive Mode (Default)

Run the main script and follow the prompts:

```bash
python new_enhanced_interactive/main.py
```

You'll be guided through:
1. Selecting the directory containing TXRM files
2. Choosing processing mode (batch or interactive)
3. Configuring output options

### Batch Mode

Process all files without confirmation:

```bash
python new_enhanced_interactive/main.py
# Select option 1 (Manual processing)
# Choose option 1 (Process all files - batch)
```

### Watch Mode

Monitor a directory for new TXRM files:

```bash
python new_enhanced_interactive/main.py
# Select option 2 (Watch mode)
```

---

## Configuration

### Environment File (.env)

Copy `.env.example` to `.env` and customize:

```bash
cp .env.example .env
```

Key settings:

```ini
# XradiaPy library path
XRADIA_PYTHON_PATH=/path/to/xradia/python

# Default directories
DEFAULT_TXRM_DIRECTORY=/path/to/txrm/files
DEFAULT_OUTPUT_DIRECTORY=/path/to/output

# Watch mode
WATCH_MODE_ENABLED=false
WATCH_DIRECTORY=/path/to/watch
WATCH_POLLING_INTERVAL=60
```

### Watch Mode Configuration

Configure watch mode interactively:

```bash
python new_enhanced_interactive/main.py
# Select option 3 (Configure watch mode)
```

### Contacts File

The `contacts.csv` file tracks metadata attribution:

```csv
name,email,uniqueID
John Smith,john.smith@example.com,1001
Jane Doe,jane.doe@example.com,1002
```

---

## Output Files

For each processed TXRM file, the tool generates:

### 1. Metadata Text File (`*_metadata.txt`)

Human-readable metadata including:
- Basic file information
- Machine settings (voltage, power, current)
- Image properties (resolution, voxel size)
- Projection data

### 2. Configuration File (`*_config.txt`)

Machine configuration parameters for reproducibility.

### 3. Cumulative CSV

Combined metadata from all processed files:
- Filename: `cumulative_metadata_YYYYMMDD_HHMMSS.csv`
- Contains standardized columns for all metadata fields
- Useful for data analysis and comparison

---

## CSV Column Reference

| Column | Description |
|--------|-------------|
| `file_name` | TXRM filename without extension |
| `ct_voxel_size_um` | Voxel size in micrometers |
| `ct_objective` | Objective lens used |
| `xray_tube_voltage` | X-ray tube voltage (kV) |
| `xray_tube_power` | X-ray tube power (W) |
| `xray_tube_current` | Calculated current (mA) |
| `ct_exposure_time` | Exposure time per projection |
| `ct_projections` | Number of projections |
| ... | See code for complete list |

---

## GitHub Integration (Optional)

Automatically push metadata updates to GitHub:

1. Generate a Personal Access Token:
   - GitHub → Settings → Developer settings → Personal access tokens
   - Generate token with `repo` scope

2. Configure in `.env`:
   ```ini
   GITHUB_ENABLED=true
   GITHUB_TOKEN=your_token_here
   GITHUB_REPO_OWNER=your_username
   GITHUB_REPO_NAME=your_repo
   GITHUB_BRANCH=main
   ```

---

## System Check

Run diagnostics to verify your setup:

```bash
python system_check.py
```

This checks:
- Python version and path
- XradiaPy installation
- Required dependencies
- Xradia software location
- File permissions

---

## Troubleshooting

### XradiaPy Import Error

```
ImportError: No module named XradiaPy
```

**Solution**: Add Xradia Python directory to PYTHONPATH:

```bash
# Windows
set PYTHONPATH=%PYTHONPATH%;C:\Program Files\Xradia\Python

# macOS/Linux
export PYTHONPATH=$PYTHONPATH:/opt/xradia/python
```

### Python Version Error

```
SyntaxError: invalid syntax
```

**Solution**: Ensure you're using Python 2.7:

```bash
python2.7 new_enhanced_interactive/main.py
```

### Permission Denied

**Solution**: 
- Windows: Run PyCharm as Administrator
- Unix: Check file permissions with `ls -la`

---

## Development

### Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest
```

### Linting

```bash
pylint new_enhanced_interactive/
```

### Mock XradiaPy

For development without Xradia software, use the mock:

```python
# The mock is at: new_enhanced_interactive/tests/mocks/XradiaPy.py
import sys
sys.path.insert(0, 'new_enhanced_interactive/tests/mocks')
```

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit your changes: `git commit -am 'Add my feature'`
4. Push to the branch: `git push origin feature/my-feature`
5. Create a Pull Request

---

## License

MIT License - see LICENSE file for details.

---

## Support

- **Documentation**: [INSTALL.md](INSTALL.md)
- **Issues**: GitHub Issues page
- **System Check**: Run `python system_check.py`

---

*X-radia Metadata Extractor - Making TXRM metadata accessible*
