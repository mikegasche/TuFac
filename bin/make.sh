#!/bin/bash

# ------------------------------------------------------------------------------
# make.sh - Build TuFac.app (macOS Intel/ARM64)
# Uses PyInstaller
# ------------------------------------------------------------------------------

set -e

# --- 0. Detect architecture ---

ARCH=$(uname -m)
echo "==> Detected architecture: $ARCH"

# --- 1. Determine project root ---

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

# --- 2. Python version ---

PYTHON_VERSION="3.14.7"

echo "==> Using Python $PYTHON_VERSION"

# --- 3. Set project-local Python version ---

pyenv local "$PYTHON_VERSION"

# Activate pyenv shims
export PATH="$HOME/.pyenv/shims:$PATH"

echo "==> Python:"
python --version
echo "==> Python executable:"
which python

# --- 4. Activate virtual environment ---

if [ ! -d "venv" ]; then
    echo "ERROR: virtual environment not found."
    echo "Run ./bin/setup.sh first."
    exit 1
fi

source venv/bin/activate

echo "==> Active Python:"
python --version
echo "==> Active Python executable:"
which python

# --- 5. Check PyInstaller ---

if ! python -m PyInstaller --version >/dev/null 2>&1; then
    echo "ERROR: PyInstaller not found."
    echo "Run ./bin/setup.sh first."
    exit 1
fi

# --- 6. Remove old builds ---

echo "==> Removing old build files..."

rm -rf build
rm -rf dist
rm -f TuFac.spec

# --- 7. Build application ---

echo "==> Building TuFac.app..."

python -m PyInstaller \
    --name "TuFac" \
    --windowed \
    --icon "app/resources/app_icon.icns" \
    --add-data "app/resources:resources" \
    app/tufac.py

echo ""
echo "==> Build finished."
echo "==> Application: dist/TuFac.app"
