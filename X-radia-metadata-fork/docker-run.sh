#!/bin/bash
# X-radia Metadata Extractor - Docker Quick Run
# ==============================================
#
# IMPORTANT: XradiaPy requires your HOST system's Python!
# This script automatically detects and mounts your Python installation.
#
# Usage:
#   ./docker-run.sh                              # Auto-detect everything
#   ./docker-run.sh /path/to/txrm/files          # Specify data path
#   ./docker-run.sh /path/to/data /path/to/python27  # Specify both

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo -e "${CYAN}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║         X-RADIA METADATA EXTRACTOR - Docker                   ║${NC}"
echo -e "${CYAN}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}[ERROR] Docker is not installed${NC}"
    echo "Install from: https://www.docker.com/get-started"
    exit 1
fi

if ! docker info &> /dev/null 2>&1; then
    echo -e "${RED}[ERROR] Docker is not running${NC}"
    echo "Please start Docker Desktop"
    exit 1
fi
echo -e "${GREEN}[OK]${NC} Docker is available"

# Parse arguments
DATA_PATH="${1:-$SCRIPT_DIR/sample_data}"
PYTHON_PATH="${2:-}"

# Auto-detect Python 2.7 with XradiaPy if not specified
if [ -z "$PYTHON_PATH" ]; then
    echo ""
    echo -e "${CYAN}Detecting host Python 2.7...${NC}"
    
    # Check common locations
    PYTHON_CANDIDATES=(
        "/usr"                                          # Linux standard
        "/usr/local"                                    # macOS Homebrew
        "/opt/local"                                    # macOS MacPorts
        "$HOME/.pyenv/versions/2.7.18"                 # pyenv
        "/Library/Frameworks/Python.framework/Versions/2.7"  # macOS Python.org
    )
    
    for candidate in "${PYTHON_CANDIDATES[@]}"; do
        if [ -x "$candidate/bin/python2.7" ] || [ -x "$candidate/bin/python" ]; then
            # Check if this Python has XradiaPy
            PYTHON_BIN="$candidate/bin/python2.7"
            [ ! -x "$PYTHON_BIN" ] && PYTHON_BIN="$candidate/bin/python"
            
            if $PYTHON_BIN -c "import XradiaPy" 2>/dev/null; then
                PYTHON_PATH="$candidate"
                echo -e "${GREEN}[OK]${NC} Found Python with XradiaPy: $PYTHON_PATH"
                break
            fi
        fi
    done
    
    if [ -z "$PYTHON_PATH" ]; then
        # Fallback: use system Python location even without XradiaPy
        if [ -x "/usr/bin/python2.7" ]; then
            PYTHON_PATH="/usr"
            echo -e "${YELLOW}[!]${NC} Using /usr Python (XradiaPy not detected)"
        else
            echo -e "${YELLOW}[!]${NC} Python 2.7 not found - container will use fallback"
        fi
    fi
fi

# Create directories
mkdir -p "$SCRIPT_DIR/sample_data" "$SCRIPT_DIR/output"

# Build image
echo ""
echo -e "${CYAN}Building Docker image...${NC}"
docker build -t xradia-metadata:latest "$SCRIPT_DIR" || {
    echo -e "${RED}[ERROR] Build failed${NC}"
    exit 1
}
echo -e "${GREEN}[OK]${NC} Image ready"

# Prepare docker command
DOCKER_CMD="docker run -it --rm"
DOCKER_CMD="$DOCKER_CMD -v $DATA_PATH:/data"
DOCKER_CMD="$DOCKER_CMD -v $SCRIPT_DIR/output:/output"
DOCKER_CMD="$DOCKER_CMD -v $SCRIPT_DIR/contacts.csv:/app/contacts.csv:ro"

if [ -n "$PYTHON_PATH" ] && [ -d "$PYTHON_PATH" ]; then
    DOCKER_CMD="$DOCKER_CMD -v $PYTHON_PATH:/host_python:ro"
fi

DOCKER_CMD="$DOCKER_CMD xradia-metadata:latest"

# Show config
echo ""
echo -e "${CYAN}Configuration:${NC}"
echo "  Data:   $DATA_PATH"
echo "  Output: $SCRIPT_DIR/output"
[ -n "$PYTHON_PATH" ] && echo "  Python: $PYTHON_PATH"

# Run
echo ""
echo -e "${CYAN}Starting container...${NC}"
echo ""
eval $DOCKER_CMD
