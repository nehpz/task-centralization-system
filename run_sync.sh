#!/bin/bash
#
# Granola Sync - Cron wrapper script
#
# This script is designed to be called by cron every 15 minutes.
# It ensures the correct environment and paths are set.
#

# Set working directory to script location
cd "$(dirname "$0")" || exit 1

# Run the sync
/usr/bin/env python3 granola_sync.py >> logs/cron.log 2>&1

# Exit with sync script's exit code
exit $?
