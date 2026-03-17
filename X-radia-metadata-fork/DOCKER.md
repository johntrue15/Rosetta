# Docker Installation Guide

Run X-radia Metadata Extractor in a Docker container.

## Important: XradiaPy Requires Host Python

**XradiaPy contains compiled binaries** that are tied to your host system's Python installation (the one that came with Xradia Software Suite). The Docker container must use your **host's Python** - not a containerized Python.

This means:
- You need Python 2.7 with XradiaPy installed on your **host machine**
- The Docker container mounts your host's Python directory
- Docker provides isolation for the app, but uses host Python for XradiaPy

---

## Prerequisites

1. **Docker Desktop** - [Download here](https://www.docker.com/get-started)
2. **Python 2.7 on host** - With XradiaPy from Xradia Software Suite

### Where is my Python 2.7?

| OS | Common Location |
|----|-----------------|
| Windows | `C:\Python27` |
| Windows (Xradia) | `C:\Program Files\Xradia\Python` |
| macOS | `/usr/local/bin/python2.7` or `/Library/Frameworks/Python.framework/Versions/2.7` |
| Linux | `/usr/bin/python2.7` (in `/usr`) |

---

## Quick Start

### Windows

```batch
REM Auto-detects Python 2.7 location
docker-run.bat C:\path\to\txrm\files

REM Or specify Python path explicitly
docker-run.bat C:\path\to\txrm\files C:\Python27
```

### Mac/Linux

```bash
# Auto-detects Python 2.7 location
./docker-run.sh /path/to/txrm/files

# Or specify Python path explicitly
./docker-run.sh /path/to/txrm/files /usr
```

The scripts will:
1. Detect your Python 2.7 installation
2. Check if XradiaPy is available
3. Mount the correct directories
4. Start the container

---

## Manual Docker Commands

### Build the Image

```bash
docker build -t xradia-metadata .
```

### Run with Host Python

**Linux:**
```bash
docker run -it --rm \
  -v /path/to/txrm/files:/data \
  -v /usr:/host_python:ro \
  -v ./output:/output \
  xradia-metadata
```

**Windows:**
```batch
docker run -it --rm ^
  -v C:\path\to\txrm\files:/data ^
  -v C:\Python27:/host_python:ro ^
  -v %cd%\output:/output ^
  xradia-metadata
```

**macOS:**
```bash
docker run -it --rm \
  -v /path/to/txrm/files:/data \
  -v /Library/Frameworks/Python.framework/Versions/2.7:/host_python:ro \
  -v ./output:/output \
  xradia-metadata
```

---

## Volume Mounts Explained

| Mount Point | Purpose | Required |
|-------------|---------|----------|
| `/data` | Your TXRM files | Yes |
| `/host_python` | Host Python 2.7 with XradiaPy | Yes (for XradiaPy) |
| `/output` | Output files (CSV, metadata) | Recommended |
| `/app/contacts.csv` | Custom contacts file | Optional |

### Critical: Host Python Mount

The `/host_python` mount must point to your Python 2.7 installation directory that contains:
```
/host_python/
├── bin/
│   ├── python          (or python.exe on Windows)
│   └── python2.7
└── lib/
    └── python2.7/
        └── site-packages/
            └── XradiaPy/   ← This is what we need!
```

---

## Docker Compose

Edit `docker-compose.yml` and uncomment the Python mount for your OS:

```yaml
volumes:
  # Your TXRM files
  - ./sample_data:/data
  
  # HOST PYTHON - uncomment ONE of these:
  # Windows:
  # - C:\Python27:/host_python:ro
  
  # Linux:
  # - /usr:/host_python:ro
  
  # macOS:
  # - /Library/Frameworks/Python.framework/Versions/2.7:/host_python:ro
  
  # Output
  - ./output:/output
```

Then run:
```bash
docker-compose run --rm xradia-metadata
```

---

## Troubleshooting

### "XradiaPy not found"

1. **Check host Python has XradiaPy:**
   ```bash
   python2.7 -c "import XradiaPy; print('OK')"
   ```

2. **Verify mount path is correct:**
   - The mounted directory should contain `bin/python2.7`
   - On Windows: mount `C:\Python27`, not `C:\Python27\python.exe`

3. **Check Xradia Software Suite installation:**
   - XradiaPy is installed as part of Zeiss Xradia software
   - It's not available via pip

### "No Python found"

The container couldn't find Python in `/host_python`. Make sure you're mounting the correct directory:

```bash
# Check your Python location first
which python2.7        # Linux/Mac
where python           # Windows

# Then mount the parent directory
docker run -v /usr:/host_python ...
```

### Container exits immediately

- Use `-it` flags for interactive mode
- Check if Python path is mounted correctly

### Permission denied

- On Linux, you may need to run with `--user $(id -u):$(id -g)`
- Check that the mounted directories are readable

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Docker Container                      │
│  ┌─────────────────────────────────────────────────┐   │
│  │              Application Code                    │   │
│  │         (new_enhanced_interactive/)             │   │
│  └─────────────────────────────────────────────────┘   │
│                         │                               │
│                         ▼                               │
│  ┌─────────────────────────────────────────────────┐   │
│  │           /host_python (mounted)                 │   │
│  │     ┌─────────────────────────────────┐        │   │
│  │     │   Host's Python 2.7 + XradiaPy  │        │   │
│  │     │   (from Xradia Software Suite)  │        │   │
│  │     └─────────────────────────────────┘        │   │
│  └─────────────────────────────────────────────────┘   │
│                         │                               │
│                         ▼                               │
│  ┌─────────────────────────────────────────────────┐   │
│  │              /data (mounted)                     │   │
│  │            Your TXRM files                       │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │   /output (mounted)   │
              │   Results saved here  │
              └───────────────────────┘
```

---

## Why This Approach?

XradiaPy is a **proprietary library** from Zeiss that:
- Contains compiled C/C++ extensions (`.so`/`.dll`/`.pyd` files)
- Is linked to specific Python versions and system libraries
- Cannot be redistributed or installed via pip
- Must be installed as part of Xradia Software Suite

By mounting the host's Python, we get:
- Access to XradiaPy with all its dependencies
- Correct binary compatibility
- No need to reverse-engineer proprietary software

---

## Alternative: Run Without Docker

If Docker + host Python mounting seems complex, consider running directly:

```bash
# Just use your system Python directly
python2.7 start.py
```

Docker is most useful when you want:
- Consistent environment across team members
- Isolation from other Python projects
- Easy deployment to servers

---

*For non-Docker installation, see [INSTALL.md](INSTALL.md)*
