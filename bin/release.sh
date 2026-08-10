#!/bin/bash
#
# TuFac Release Script
#
# Creates a git tag and pushes it to GitHub.
# This triggers the GitHub Actions workflow (build-release.yml) which
# builds the Windows and macOS packages on GitHub and creates a GitHub
# Release with the packages attached as assets.
#
# Usage:
#   ./bin/release.sh 1.0.0
#

set -e

if [ -z "$1" ]; then
    echo "Usage: ./bin/release.sh <version>"
    echo "Example: ./bin/release.sh 1.0.0"
    exit 1
fi

VERSION="$1"

# Validate version format (e.g. 1.0.0, 1.0.1-beta.1)
if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$ ]]; then
    echo "Invalid version format: $VERSION"
    echo "Expected format: X.Y.Z (e.g. 1.0.0, 1.0.1-beta.1)"
    exit 1
fi

echo "=== TuFac Release ==="
echo ""

# Check for uncommitted changes
if ! git diff --quiet 2>/dev/null; then
    echo "You have uncommitted changes. Please commit first."
    exit 1
fi

echo "Tagging v${VERSION}..."
git tag "v${VERSION}"

echo "Pushing tags..."
git push --tags

echo ""
echo "=== Done! ==="
echo "GitHub Actions will now build and publish:"
echo "  - TuFac Windows package (v${VERSION})"
echo "  - TuFac macOS Intel package (v${VERSION})"
echo "  - TuFac macOS ARM64 package (v${VERSION})"
echo "  - GitHub Release (v${VERSION})"
echo ""
