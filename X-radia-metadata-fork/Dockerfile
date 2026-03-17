# X-radia Metadata Extractor - Docker Image
# ==========================================
#
# IMPORTANT: XradiaPy requires the HOST system's Python environment
# because it contains compiled binaries tied to the Xradia installation.
#
# This Dockerfile provides TWO modes:
#   1. Standalone mode (without XradiaPy) - for testing/development
#   2. Host Python mode - mounts host's Python with XradiaPy
#
# For full XradiaPy support, use docker-run.sh/bat which mounts host Python.

FROM ubuntu:20.04

LABEL maintainer="X-radia Metadata Team"
LABEL description="X-radia Metadata Extractor - TXRM file metadata processing"
LABEL version="1.0.0"

# Prevent interactive prompts during build
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV APP_HOME=/app
ENV DATA_DIR=/data

# Install minimal dependencies
# Python is intentionally NOT installed - we use host's Python for XradiaPy
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR ${APP_HOME}

# Copy application code only (no Python runtime)
COPY new_enhanced_interactive/ ./new_enhanced_interactive/
COPY scripts/ ./scripts/
COPY *.py ./
COPY *.csv ./
COPY *.txt ./
COPY *.md ./

# Create mount points
RUN mkdir -p ${DATA_DIR} /output /host_python

# Create entrypoint that uses HOST Python
RUN cat > /entrypoint.sh << 'ENTRYPOINT_EOF'
#!/bin/bash
set -e

echo ""
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║         X-RADIA METADATA EXTRACTOR (Docker)                   ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""

# Check for host Python mount
if [ -x "/host_python/bin/python" ] || [ -x "/host_python/bin/python2.7" ]; then
    if [ -x "/host_python/bin/python2.7" ]; then
        PYTHON_CMD="/host_python/bin/python2.7"
    else
        PYTHON_CMD="/host_python/bin/python"
    fi
    echo "[OK] Using host Python: $PYTHON_CMD"
    
    # Set up Python path for host Python
    export PATH="/host_python/bin:$PATH"
    export PYTHONPATH="${APP_HOME}:${PYTHONPATH}"
    
    # Check XradiaPy
    if $PYTHON_CMD -c "import XradiaPy" 2>/dev/null; then
        echo "[OK] XradiaPy is available"
    else
        echo "[!] XradiaPy not found in host Python"
        echo "    Make sure your host Python has XradiaPy installed"
    fi
    
elif command -v python2.7 &> /dev/null; then
    PYTHON_CMD="python2.7"
    echo "[OK] Using system Python 2.7"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
    echo "[!] Using fallback Python (XradiaPy may not work)"
else
    echo "[ERROR] No Python found!"
    echo ""
    echo "Mount your host Python directory:"
    echo "  -v /path/to/python27:/host_python"
    echo ""
    echo "Or on Windows with Xradia installed:"
    echo "  -v C:\\Python27:/host_python"
    exit 1
fi

# Check data directory
if [ -d "/data" ] && [ "$(ls -A /data 2>/dev/null)" ]; then
    echo "[OK] Data directory mounted at /data"
    TXRM_COUNT=$(find /data -iname "*.txrm" 2>/dev/null | wc -l)
    echo "    Found $TXRM_COUNT TXRM file(s)"
else
    echo "[!] No data mounted at /data"
fi
echo ""

# Execute command with the correct Python
if [ "$#" -eq 0 ]; then
    exec $PYTHON_CMD ${APP_HOME}/new_enhanced_interactive/main.py
else
    exec "$@"
fi
ENTRYPOINT_EOF
chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD []
