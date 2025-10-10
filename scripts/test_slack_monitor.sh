#!/bin/bash
#
# Test Slack CDP Monitor
#
# This script tests the monitor for 3 iterations (3 minutes with 60s interval)
# to verify it's working before deploying as a service.

set -e

echo "================================================"
echo "🧪 Testing Slack CDP Monitor"
echo "================================================"

# Check if Slack is running with debug port
if ! pgrep -f "Slack.*remote-debugging-port" >/dev/null; then
  echo "❌ Slack is not running with remote debugging port!"
  echo ""
  echo "Please run:"
  echo "  killall Slack"
  echo "  /Applications/Slack.app/Contents/MacOS/Slack --remote-debugging-port=9222 &"
  echo ""
  exit 1
fi

echo "✅ Slack is running with debug port"
echo ""

# Get vault path
VAULT_PATH="${OBSIDIAN_VAULT_PATH:-$HOME/Obsidian/zenyth}"

if [ ! -d "$VAULT_PATH" ]; then
  echo "❌ Vault not found: $VAULT_PATH"
  echo ""
  echo "Set OBSIDIAN_VAULT_PATH environment variable or update script"
  exit 1
fi

echo "✅ Vault found: $VAULT_PATH"
echo ""

# Run monitor for 3 iterations (test mode)
echo "🚀 Running monitor for 3 iterations (~ 3 minutes)..."
echo "   (Press Ctrl+C to stop early)"
echo ""

cd "$(dirname "$0")/.."

python src/slack_cdp_monitor.py \
  --vault "$VAULT_PATH" \
  --interval 60 \
  --max-iterations 3

echo ""
echo "================================================"
echo "✅ Test Complete!"
echo "================================================"
echo ""
echo "Check results in:"
echo "  $VAULT_PATH/00_Inbox/Slack/$(date +%Y-%m-%d) - Slack Captures.md"
echo ""
echo "If successful, deploy as service with:"
echo "  ./scripts/deploy_slack_monitor.sh"
echo ""
