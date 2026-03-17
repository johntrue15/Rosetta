# Installation Guide

Complete installation guide for the X-radia Metadata Extractor, optimized for users downloading from GitHub and using PyCharm.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Prerequisites](#prerequisites)
3. [Download Options](#download-options)
4. [PyCharm Setup](#pycharm-setup)
5. [Python Configuration](#python-configuration)
6. [XradiaPy Installation](#xradiaPy-installation)
7. [Verification](#verification)
8. [Troubleshooting](#troubleshooting)

---

## Quick Start

For experienced users:

```bash
# 1. Download and extract (or clone)
# 2. Run system check
python system_check.py

# 3. Run setup wizard
python setup_wizard.py

# 4. Start processing
python new_enhanced_interactive/main.py
```

---

## Prerequisites

### Required Software

| Software | Version | Purpose |
|----------|---------|---------|
| Python | 2.7.x | Runtime (XradiaPy compatibility) |
| PyCharm | Any | Recommended IDE |
| Xradia Software Suite | - | Provides XradiaPy library |

### System Requirements

- **Operating System**: Windows 7+, macOS 10.12+, or Linux
- **RAM**: 4GB minimum (8GB+ recommended for large files)
- **Disk Space**: 100MB for the tool + space for output files

---

## Download Options

### Option 1: Download ZIP (Easiest)

1. Go to the GitHub repository
2. Click the green **Code** button
3. Select **Download ZIP**
4. Extract to a folder of your choice (e.g., `C:\Projects\X-radia-metadata` or `~/Projects/X-radia-metadata`)

### Option 2: Clone with Git

```bash
git clone https://github.com/yourusername/X-radia-metadata.git
cd X-radia-metadata
```

---

## PyCharm Setup

### Step 1: Open the Project

1. Launch PyCharm
2. Go to **File → Open**
3. Navigate to the extracted/cloned folder
4. Click **OK** to open the project

### Step 2: Configure Python Interpreter

1. Go to **File → Settings** (Windows/Linux) or **PyCharm → Preferences** (macOS)
2. Navigate to **Project: X-radia-metadata → Python Interpreter**
3. Click the gear icon ⚙️ → **Add...**
4. Select **System Interpreter** or **Existing environment**
5. Browse to your Python 2.7 installation:
   - **Windows**: `C:\Python27\python.exe`
   - **macOS**: `/usr/local/bin/python2.7` or `~/.pyenv/versions/2.7.18/bin/python`
   - **Linux**: `/usr/bin/python2.7`
6. Click **OK**

### Step 3: Add XradiaPy to Path

1. In the Python Interpreter settings, click **Show All...**
2. Select your interpreter and click the folder icon (Show paths)
3. Click **+** to add a path
4. Add the Xradia Python directory:
   - **Windows**: `C:\Program Files\Xradia\Python` or similar
   - **macOS/Linux**: `/opt/xradia/python` or similar
5. Click **OK** to save

### Step 4: Run the System Check

1. In PyCharm, right-click on `system_check.py`
2. Select **Run 'system_check'**
3. Review the output for any issues

---

## Python Configuration

### Installing Python 2.7

#### Windows

1. Download Python 2.7.18 from [python.org](https://www.python.org/downloads/release/python-2718/)
2. Run the installer
3. **Important**: Check "Add Python to PATH"
4. Complete the installation

#### macOS

Using Homebrew (recommended):
```bash
brew install python@2
```

Using pyenv:
```bash
brew install pyenv
pyenv install 2.7.18
pyenv global 2.7.18
```

#### Linux (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install python2.7 python2.7-dev python-pip
```

### Installing Dependencies

Run from the project directory:

```bash
pip install -r requirements.txt
```

Or use the setup wizard:

```bash
python setup_wizard.py
```

---

## XradiaPy Installation

XradiaPy is a proprietary library from Zeiss/Xradia that must be installed separately.

### Step 1: Install Xradia Software Suite

1. Obtain the Xradia Software Suite installer from Zeiss
2. Run the installer
3. **Important**: Ensure Python bindings are selected during installation

### Step 2: Locate the Python Library

After installation, find the XradiaPy library location:

| OS | Typical Location |
|----|------------------|
| Windows | `C:\Program Files\Xradia\Python` |
| Windows (x86) | `C:\Program Files (x86)\Zeiss\Xradia\Python` |
| macOS | `/Applications/Xradia/Python` |
| Linux | `/opt/xradia/python` |

### Step 3: Add to PYTHONPATH

#### Option A: System Environment Variable

**Windows:**
1. Right-click **This PC** → **Properties**
2. Click **Advanced system settings**
3. Click **Environment Variables**
4. Under **System variables**, find or create `PYTHONPATH`
5. Add the Xradia Python directory path

**macOS/Linux:**
Add to your shell profile (`~/.bashrc`, `~/.zshrc`, etc.):
```bash
export PYTHONPATH="$PYTHONPATH:/path/to/xradia/python"
```

#### Option B: PyCharm Project Settings

See [Step 3 in PyCharm Setup](#step-3-add-xradiaPy-to-path)

#### Option C: .env File

Copy `.env.example` to `.env` and set:
```
XRADIA_PYTHON_PATH=/path/to/xradia/python
```

---

## Verification

### Run the System Check

```bash
python system_check.py
```

Expected output for a correctly configured system:

```
============================================================
  X-radia Metadata Extractor - System Check
============================================================

Python Environment
============================================================
Python Version: 2.7.18
Python Path: /usr/bin/python2.7
Platform: Darwin-21.6.0-x86_64-i386-64bit
[OK] Python 2.7 detected - Compatible with XradiaPy

XradiaPy Library
============================================================
[OK] XradiaPy is installed and importable
[OK] XradiaPy.Data module available

...

System check PASSED - Ready to run!
```

### Run a Test

```bash
python new_enhanced_interactive/main.py
```

---

## Troubleshooting

### Common Issues

#### "ModuleNotFoundError: No module named 'XradiaPy'"

**Cause**: XradiaPy is not in the Python path.

**Solutions**:
1. Verify Xradia Software Suite is installed
2. Add the Xradia Python directory to PYTHONPATH
3. Check the path in PyCharm interpreter settings

#### "SyntaxError: invalid syntax"

**Cause**: Using Python 3 instead of Python 2.7.

**Solutions**:
1. Verify you're using Python 2.7: `python --version`
2. Use the full path to Python 2.7: `/usr/bin/python2.7 main.py`
3. Set up a Python 2.7 interpreter in PyCharm

#### "Permission denied"

**Cause**: Insufficient permissions to read TXRM files or write output.

**Solutions**:
1. Run PyCharm as Administrator (Windows)
2. Check file/folder permissions
3. Choose an output directory you have write access to

#### "ImportError: DLL load failed"

**Cause**: Missing Windows DLL dependencies.

**Solutions**:
1. Install Visual C++ Redistributable
2. Ensure Xradia software is fully installed
3. Restart your computer after installation

### Getting Help

If you encounter issues not covered here:

1. Run `python system_check.py` and save the output
2. Check the project's GitHub Issues page
3. Contact the project maintainers with:
   - System check output
   - Steps to reproduce the issue
   - Any error messages

---

## Project Structure

After setup, your project should look like:

```
X-radia-metadata/
├── .env                          # Your local configuration (created from .env.example)
├── .env.example                  # Configuration template
├── .idea/                        # PyCharm project files
│   └── runConfigurations/        # Run configurations
├── contacts.csv                  # Contact information file
├── INSTALL.md                    # This file
├── main.py                       # Legacy entry point
├── new_enhanced_interactive/     # Main package
│   ├── config/                   # Configuration modules
│   ├── metadata/                 # Metadata extraction
│   ├── processors/               # File processors
│   └── utils/                    # Utilities
├── Readme.md                     # Main documentation
├── requirements.txt              # Python dependencies
├── scripts/                      # Legacy standalone scripts
├── setup.py                      # Package setup
├── setup_wizard.py               # Interactive setup wizard
└── system_check.py               # System diagnostics
```

---

## Next Steps

After successful installation:

1. **Read the Documentation**: See `Readme.md` for usage instructions
2. **Configure Watch Mode**: Set up automatic file monitoring
3. **Set Up Contacts**: Edit `contacts.csv` with your team information
4. **Optional**: Configure GitHub integration for automatic metadata backup

---

*Last updated: February 2026*
