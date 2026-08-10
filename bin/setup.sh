#!/bin/bash

# ------------------------------------------------------------------------------
# setup.sh
#
# macOS (Intel/ARM64) - Python environment, venv, packages
# ------------------------------------------------------------------------------

set -e

# --- 0. Detect architecture ---

ARCH=$(uname -m)
echo "==> Detected architecture: $ARCH"

# --- 1. Determine project root (bin/ is parallel to app/) ---

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

# --- 2. Ensure pyenv is installed ---

if ! command -v pyenv >/dev/null 2>&1; then
    echo "ERROR: pyenv not found. Install pyenv first."
    exit 1
fi

# --- 3. Clean up old environment variables ---

unset PYTHON_CONFIGURE_OPTS
unset CONFIGURE_OPTS
unset LDFLAGS
unset CPPFLAGS
unset PKG_CONFIG_PATH

# Remove old pyenv patches if present
rm -rf "$HOME/.pyenv/patches" 2>/dev/null || true

# --- 4. Python version ---

PYTHON_VERSION="3.14.7"

echo "==> Using Python $PYTHON_VERSION"

# Check whether this Python version is available in pyenv
if ! pyenv install -l | sed 's/^[[:space:]]*//' | grep -qx "$PYTHON_VERSION"; then
    echo "ERROR: Python $PYTHON_VERSION is not available in pyenv."
    echo "Available versions:"
    pyenv install -l | grep -E '^ *3\.14'
    exit 1
fi

echo "==> Installing Python $PYTHON_VERSION via pyenv..."
pyenv install -s "$PYTHON_VERSION"

# Set project-local Python version
pyenv local "$PYTHON_VERSION"

# Activate pyenv shims
export PATH="$HOME/.pyenv/shims:$PATH"

echo "==> Python:"
python --version
echo "==> Python path:"
which python

# --- 5. Remove old venv ---

echo "==> Removing old venv..."
rm -rf venv

# --- 6. Create new venv ---

echo "==> Creating new venv..."
python -m venv venv

source venv/bin/activate

# --- 7. Upgrade packaging tools ---

echo "==> Upgrading pip, setuptools, wheel..."
python -m pip install --upgrade pip setuptools wheel

# --- 8. Install required packages ---

echo "==> Installing required packages..."
python -m pip install PySide6 pyinstaller qrcode[pil] opencv-python zxing-cpp pyotp

# --- 9. Check installed packages ---

echo "==> Installed packages:"
python -m pip show PySide6
python -m pip show pyinstaller

echo "==> Python:"
python --version

echo "==> Python executable:"
which python

echo ""
echo "==> Setup complete."
echo "==> You can now run ./bin/make.sh to build the app."
