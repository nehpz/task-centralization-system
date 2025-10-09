#!/bin/bash
#
# Granola Sync - Cron wrapper script
#
# This script is designed to be called by cron every 15 minutes.
# It ensures the correct environment and paths are set.
#

# Set working directory to project root (parent of scripts/)
cd "$(dirname "$0")/.." || exit 1

# Set PATH to include Homebrew binaries (needed for uv)
export PATH="/opt/homebrew/bin:$PATH"

# Run the sync
./scripts/granola_sync.py >>logs/cron.log 2>&1

# Exit with sync script's exit code
exit $?
