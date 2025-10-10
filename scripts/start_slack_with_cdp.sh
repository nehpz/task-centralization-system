#!/bin/bash
#
# Start Slack with Chrome DevTools Protocol Enabled
#
# This script ensures Slack runs with remote debugging enabled,
# which is required for the CDP monitor to work.

set -e

echo "🚀 Starting Slack with CDP enabled..."
echo ""

# Check if Slack is already running with debug port
if pgrep -f "Slack.*remote-debugging-port" >/dev/null; then
  echo "✅ Slack is already running with debug port"
  echo ""
  PID=$(pgrep -f "Slack.*remote-debugging-port")
  echo "   PID: $PID"
  echo ""
  exit 0
fi

# Check if Slack is running without debug port
if pgrep -i "Slack" >/dev/null; then
  echo "⚠️  Slack is running WITHOUT debug port"
  echo ""
  read -p "Kill and restart with debug port? (y/N) " -n 1 -r
  echo
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🛑 Stopping Slack..."
    killall Slack || true
    sleep 2
    echo "✅ Slack stopped"
  else
    echo "Cancelled"
    exit 1
  fi
fi

# Start Slack with debug port
echo "🚀 Starting Slack with remote debugging port 9222..."
echo ""

/Applications/Slack.app/Contents/MacOS/Slack --remote-debugging-port=9222 &

sleep 3

# Verify it started
if pgrep -f "Slack.*remote-debugging-port" >/dev/null; then
  echo "✅ Slack started successfully with CDP enabled"
  echo ""
  PID=$(pgrep -f "Slack.*remote-debugging-port")
  echo "   PID: $PID"
  echo "   Debug port: 9222"
  echo ""
  echo "💡 The Slack CDP monitor can now connect to Slack"
else
  echo "❌ Failed to start Slack with debug port"
  exit 1
fi
