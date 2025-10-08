#!/bin/bash
#
# Install Cron Job for Granola Sync
#
# This script adds a cron job to run granola_sync every 15 minutes.
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SYNC_SCRIPT="$SCRIPT_DIR/run_sync.sh"

echo "📅 Installing Granola Sync cron job..."
echo ""
echo "Script location: $SYNC_SCRIPT"
echo "Schedule: Every 15 minutes"
echo ""

# Check if script exists
if [ ! -f "$SYNC_SCRIPT" ]; then
  echo "❌ Error: $SYNC_SCRIPT not found"
  exit 1
fi

# Check if script is executable
if [ ! -x "$SYNC_SCRIPT" ]; then
  echo "❌ Error: $SYNC_SCRIPT is not executable"
  echo "Run: chmod +x $SYNC_SCRIPT"
  exit 1
fi

# Create cron entry
CRON_ENTRY="*/15 * * * * $SYNC_SCRIPT"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -F "$SYNC_SCRIPT" >/dev/null; then
  echo "⚠️  Cron job already exists:"
  crontab -l | grep -F "$SYNC_SCRIPT"
  echo ""
  read -r -p "Replace existing cron job? (yes/no): " replace
  if [[ ! "$replace" =~ ^[Yy] ]]; then
    echo "Installation cancelled."
    exit 0
  fi

  # Remove old entry
  crontab -l | grep -v -F "$SYNC_SCRIPT" | crontab -
  echo "✓ Removed old cron job"
fi

# Add new cron entry
(
  crontab -l 2>/dev/null
  echo "$CRON_ENTRY"
) | crontab -

echo ""
echo "✅ Cron job installed successfully!"
echo ""
echo "Cron entry:"
echo "  $CRON_ENTRY"
echo ""
echo "This will run granola_sync.py every 15 minutes."
echo ""
echo "📋 Useful commands:"
echo "  View cron jobs:    crontab -l"
echo "  Edit cron jobs:    crontab -e"
echo "  Remove this job:   crontab -l | grep -v '$SYNC_SCRIPT' | crontab -"
echo "  View sync logs:    tail -f $SCRIPT_DIR/logs/granola_sync.log"
echo "  View cron logs:    tail -f $SCRIPT_DIR/logs/cron.log"
echo "  Check sync status: cat $SCRIPT_DIR/.sync_status.json"
echo ""
echo "⏰ Next sync will run at the next 15-minute mark (XX:00, XX:15, XX:30, XX:45)"
echo ""
