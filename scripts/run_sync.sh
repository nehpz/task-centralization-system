#!/bin/bash
#
# Granola Sync - Cron wrapper script
#
# This script is designed to be called by cron every 15 minutes.
# It ensures the correct environment and paths are set.
#

set -e

# Set working directory to project root (parent of scripts/)
cd "$(dirname "$0")/.." || exit 1

# Common UV installation paths (script-level for error message reuse)
COMMON_UV_PATHS=(
  "/opt/homebrew/bin/uv" # Homebrew on Apple Silicon
  "/usr/local/bin/uv"    # Homebrew on Intel Mac, or manual install
  "$HOME/.cargo/bin/uv"  # Cargo/rustup install
  "$HOME/.local/bin/uv"  # pipx or local install
)

# Detect uv location using a fallback strategy
# This ensures the script works across different installation methods and platforms
detect_uv_path() {
  # 1. Check if UV_PATH is explicitly set (user override)
  if [ -n "$UV_PATH" ] && [ -x "$UV_PATH" ]; then
    echo "$UV_PATH"
    return 0
  fi

  # 2. Check if uv is already in PATH (most common)
  # Capture output in one call to avoid redundant execution
  if uv_path=$(command -v uv 2>/dev/null); then
    echo "$uv_path"
    return 0
  fi

  # 3. Check common installation locations
  for path in "${COMMON_UV_PATHS[@]}"; do
    if [ -x "$path" ]; then
      echo "$path"
      return 0
    fi
  done

  # 4. Not found
  return 1
}

# Try to detect uv
if UV_BIN=$(detect_uv_path); then
  # Add uv's directory to PATH
  UV_DIR=$(dirname "$UV_BIN")

  # Safety check: ensure UV_DIR is not empty
  if [ -z "$UV_DIR" ]; then
    echo "ERROR: Failed to determine uv directory from: $UV_BIN" >>logs/cron.log 2>&1
    exit 1
  fi

  export PATH="$UV_DIR:$PATH"
else
  # Log error and exit
  {
    echo "ERROR: uv not found in any common location"
    echo "Checked:"
    echo "  - UV_PATH environment variable"
    echo "  - Current PATH"
    # Dynamically list checked paths to avoid duplication
    for path in "${COMMON_UV_PATHS[@]}"; do
      echo "  - $path"
    done
    echo ""
    echo "To fix this:"
    echo "  1. Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo "  2. Or set UV_PATH: export UV_PATH=/path/to/uv"
    echo "  3. Or add uv to your PATH"
  } >>logs/cron.log 2>&1
  exit 1
fi

# Run the sync
./scripts/granola_sync.py >>logs/cron.log 2>&1

# Exit with sync script's exit code
exit $?
