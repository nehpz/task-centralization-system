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

# Detect uv location using a fallback strategy
# This ensures the script works across different installation methods and platforms
detect_uv_path() {
  # 1. Check if UV_PATH is explicitly set (user override)
  if [ -n "$UV_PATH" ] && [ -x "$UV_PATH" ]; then
    echo "$UV_PATH"
    return 0
  fi

  # 2. Check if uv is already in PATH (most common)
  if command -v uv >/dev/null 2>&1; then
    command -v uv
    return 0
  fi

  # 3. Check common installation locations
  local common_paths=(
    "/opt/homebrew/bin/uv" # Homebrew on Apple Silicon
    "/usr/local/bin/uv"    # Homebrew on Intel Mac, or manual install
    "$HOME/.cargo/bin/uv"  # Cargo/rustup install
    "$HOME/.local/bin/uv"  # pipx or local install
  )

  for path in "${common_paths[@]}"; do
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
  export PATH="$UV_DIR:$PATH"
else
  # Log error and exit
  {
    echo "ERROR: uv not found in any common location"
    echo "Checked:"
    echo "  - UV_PATH environment variable"
    echo "  - Current PATH"
    echo "  - /opt/homebrew/bin/uv (Homebrew Apple Silicon)"
    echo "  - /usr/local/bin/uv (Homebrew Intel)"
    echo "  - $HOME/.cargo/bin/uv (Cargo)"
    echo "  - $HOME/.local/bin/uv (Local install)"
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
