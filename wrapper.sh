#!/bin/bash
# wrapper.sh - EPG Transformation Pipeline for Termux

set -e # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== EPG Transformation Module ==="

# 1. Environment Setup
if [ ! -d "venv" ]; then
    echo "[Setup] Creating virtual environment..."
    python -m venv venv
    echo "[Setup] Installing dependencies (lxml, PyYAML)..."
    ./venv/bin/pip install --no-cache-dir lxml PyYAML
else
    echo "[Check] Virtual environment found."
fi

# 2. Pre-flight Checks
if [ ! -f "guide.xml" ]; then
    echo "[Error] Raw input 'guide.xml' not found. Aborting."
    exit 1
fi

if [ ! -f "config.yaml" ]; then
    echo "[Error] Configuration 'config.yaml' not found. Aborting."
    exit 1
fi

# 3. Execution
echo "[Run] Starting transformation..."
if ./venv/bin/python epg_transform.py; then
    echo "[Success] EPG update complete. Output: guide_filtered.xml"
    # Optional: Verify file size is non-zero
    if [ ! -s "guide_filtered.xml" ]; then
        echo "[Warning] Output file is empty. Check filter rules."
    fi
else
    echo "[Fail] EPG update failed. Check logs."
    exit 1
fi
