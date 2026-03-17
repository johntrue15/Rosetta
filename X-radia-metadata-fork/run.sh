#!/bin/bash
# X-radia Metadata Extractor - Quick Start
# Run: ./run.sh

cd "$(dirname "$0")"

# Find Python
if command -v python2.7 &> /dev/null; then
    python2.7 start.py
elif command -v python2 &> /dev/null; then
    python2 start.py
elif command -v python &> /dev/null; then
    python start.py
elif command -v python3 &> /dev/null; then
    python3 start.py
else
    echo ""
    echo "[ERROR] Python not found!"
    echo ""
    echo "Please install Python:"
    echo "  macOS:  brew install python"
    echo "  Ubuntu: sudo apt install python3"
    echo ""
    exit 1
fi
