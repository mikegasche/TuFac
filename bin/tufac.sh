#!/bin/bash

# ------------------------------------------------------------------------------
# tufac.sh - Run TuFac
# ------------------------------------------------------------------------------

# Change to project root
cd "$(dirname "$0")/.." || exit 1

# Check virtual environment
if [ ! -d "venv" ]; then
    echo "ERROR: virtual environment not found."
    echo "Run ./bin/setup.sh first."
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Run TuFac
python app/tufac.py
