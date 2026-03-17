# amnh-zeiss-utils

Utilities for handling Zeiss txm and txrm files. These python scripts allow
extraction of metadata from unreconstructed ('`txrm`') files, as well as
converting reconstructed ('`txm`') files to TIFF stacks or NRRD files.

It is assumed that you are familiar with running python scripts from the command
line and setting up conda environments. A YAML file (`amnh-zeiss-utils.yaml`) is
included with the required packages. (But see Requirements section, below.)

Note that this program does not rely on any Zeiss proprietary libraries and is
standalone (apart from setting up python dependencies in an environment, see
below) and you can run it on any machine. This means that changes to Zeiss'
proprietary file format may break this code.

This program uses code from the xrmreader package, which is available through
PyPi as a pip installable package *but* a repository appears to be not generally
available. Special thanks to Dr. Mareike Thies for the xrmreader source files.
Modifications were made to `reader.py` to parse the objective fields. These
files are included here but may be removed at any time. 

## Programs

### `txrm-monitor.py`

A PySide6 GUI application that monitors directories for new `.txrm` files and
automatically extracts metadata when files are stable. This was implemented
using Claude Sonnet 4.5 and 4.6 inside VS Code with Github copilot.

![TXRM Monitor UI](UI%20screenshot.png)

**Features:**
- Monitors configured directories recursively (scans subdirectories)
- Scans for new `.txrm` files every 5 minutes
- Tracks file size changes with 10-minute stability window
- Automatically extracts metadata using `xrmreader` when files are stable
- Saves metadata to `.txrm.txt` files alongside source files
- Daily-rotated logging to `logs/` directory
- Real-time log viewer in GUI
- Status bar showing current scanning/processing activity
- Countdown timer for next scan
- Manual "Scan Now" button for immediate scanning
- JSON-based configuration for persistent directory list (`txrm-monitor-config.json`)

**Usage:**

```bash
python txrm-monitor.py
```

The application provides a graphical interface where you can:
1. Add/remove directories to monitor
2. View the list of monitored files and their status
3. See real-time log output
4. Trigger manual scans

The window can be minimized while the application continues to run in the background. Closing the window exits the application.

### `get-metadata-from-txrm.py`


    usage: get-metadata-from-txrm.py [-h] -i INPUT_TXRM_FILE [-o OUTPUT_FILE] [-v] [-f FIELDS]

    Extract metadata from a Zeiss txrm file.

    options:
        -h, --help            show this help message and exit
        -i INPUT_TXRM_FILE, --input-txrm-file INPUT_TXRM_FILE
                                Input Zeiss txrm file
        -o OUTPUT_FILE, --output-file OUTPUT_FILE
                                Output file to save metadata
        -v, --verbose         Enable verbose output
        -f FIELDS, --fields FIELDS
                                Comma-separated list of fields to extract


### `txm-to-nrrd.py`

    usage: txm-to-nrrd.py [-h] -i INPUT_TXM_FILE -o OUTPUT_NRRD_FILE [-v]

    Convert reconstructed Zeiss txm to NRRD format.

    options:
        -h, --help            show this help message and exit
        -i INPUT_TXM_FILE, --input-txm-file INPUT_TXM_FILE
                                Input Zeiss txm file
        -o OUTPUT_NRRD_FILE, --output-nrrd-file OUTPUT_NRRD_FILE
                                Output NRRD file to save data
        -v, --verbose         Enable verbose output

### `txm-to-tiff.py`

    usage: txm-to-tiff.py [-h] -i INPUT_TXM_FILE [-p PREFIX] [-o OUTPUT_DIR] [-v]

    Convert reconstructed Zeiss txm to TIFF format.

    options:
        -h, --help            show this help message and exit
        -i INPUT_TXM_FILE, --input-txm-file INPUT_TXM_FILE
                                Input Zeiss txm file
        -p PREFIX, --prefix PREFIX
                                Filename prefix for output TIFF files
        -o OUTPUT_DIR, --output-dir OUTPUT_DIR
                                Output directory for TIFF files
        -v, --verbose         Enable verbose output


## Requirements

This repo contains a `amnh-zeiss-utils.yaml` file for creating an environment
with the required packages (and some extras that were used in development, such
as Jupyter notebook support). To be honest, I've had varying success with these
setups. If this doesn't work, just keep running the scripts, installing what is
missing as you go.

## Known issues

The "Objective" field in the txrm file is parsed using a modified version of the
xrmreader package, as discussed above.

## Contact

Hollister Herhold, PhD  
Research Associate, Division of Invertebrate Zoology  
Research Scientist, Department of Astrophysics
Research Scientist, Department of Vertebrate Paleontology
American Museum of Natural History  
hherhold@amnh.org  


