#!/bin/bash
#
# Deploy Slack CDP Monitor as launchd Service
#
# This script:
# 1. Sets up the PERPLEXITY_API_KEY from environment
# 2. Creates the launchd plist with correct paths
# 3. Loads the service
# 4. Checks service status

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PLIST_TEMPLATE="$PROJECT_ROOT/deployment/com.rzp.slack-monitor.plist"
PLIST_INSTALL="$HOME/Library/LaunchAgents/com.rzp.slack-monitor.plist"
SERVICE_NAME="com.rzp.slack-monitor"

echo "================================================"
echo "🚀 Deploying Slack CDP Monitor Service"
echo "================================================"
echo ""

# Check prerequisites
echo "📋 Checking prerequisites..."
echo ""

# 1. Check if Slack is running with debug port
if pgrep -f "Slack.*remote-debugging-port" >/dev/null; then
  echo "✅ Slack is running with debug port"
else
  echo "⚠️  Slack is NOT running with debug port"
  echo ""
  echo "The monitor requires Slack to be running with:"
  echo "  /Applications/Slack.app/Contents/MacOS/Slack --remote-debugging-port=9222 &"
  echo ""
  read -p "Do you want to continue anyway? (y/N) " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Deployment cancelled"
    exit 1
  fi
fi

# 2. Check for PERPLEXITY_API_KEY
if [ -z "$PERPLEXITY_API_KEY" ]; then
  echo "❌ PERPLEXITY_API_KEY not set in environment"
  echo ""
  echo "Please set it with:"
  echo "  export PERPLEXITY_API_KEY='your-key-here'"
  echo ""
  echo "Or add to your shell profile (~/.zshrc or ~/.bashrc):"
  echo "  export PERPLEXITY_API_KEY='your-key-here'"
  exit 1
fi

echo "✅ PERPLEXITY_API_KEY is set"

# 3. Check if uv is installed
if ! command -v uv &>/dev/null; then
  echo "❌ uv not found in PATH"
  echo ""
  echo "Install with:"
  echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
  exit 1
fi

echo "✅ uv is installed"

# 4. Check vault path
VAULT_PATH="$HOME/Obsidian/zenyth"
if [ ! -d "$VAULT_PATH" ]; then
  echo "❌ Vault not found: $VAULT_PATH"
  exit 1
fi

echo "✅ Vault found: $VAULT_PATH"
echo ""

# Create logs directory
echo "📁 Creating logs directory..."
mkdir -p "$PROJECT_ROOT/logs"
echo "✅ Logs directory ready"
echo ""

# Stop existing service if running
echo "🛑 Stopping existing service (if running)..."
if launchctl list | grep -q "$SERVICE_NAME"; then
  launchctl unload "$PLIST_INSTALL" 2>/dev/null || true
  sleep 2
  echo "✅ Existing service stopped"
else
  echo "ℹ️  No existing service found"
fi
echo ""

# Create plist with API key
echo "📝 Creating service configuration..."

# Get uv path
UV_PATH=$(which uv)

# Create the plist file with actual API key
sed "s|__REPLACE_WITH_ACTUAL_KEY__|$PERPLEXITY_API_KEY|g" "$PLIST_TEMPLATE" |
  sed "s|/Users/stephen/.local/bin/uv|$UV_PATH|g" >"$PLIST_INSTALL"

echo "✅ Service configuration created at:"
echo "   $PLIST_INSTALL"
echo ""

# Load the service
echo "🚀 Loading service..."
launchctl load "$PLIST_INSTALL"
sleep 2
echo "✅ Service loaded"
echo ""

# Check service status
echo "📊 Service Status:"
echo "================================================"

if launchctl list | grep -q "$SERVICE_NAME"; then
  echo "✅ Service is running"
  echo ""

  # Show process info
  PID=$(launchctl list | grep "$SERVICE_NAME" | awk '{print $1}')
  if [ "$PID" != "-" ]; then
    echo "   PID: $PID"
    echo "   Logs: $PROJECT_ROOT/logs/slack_monitor_stdout.log"
    echo "   Errors: $PROJECT_ROOT/logs/slack_monitor_stderr.log"
  fi
else
  echo "❌ Service is not running"
  echo ""
  echo "Check logs for errors:"
  echo "  tail -f $PROJECT_ROOT/logs/slack_monitor_stderr.log"
fi

echo ""
echo "================================================"
echo "✅ Deployment Complete!"
echo "================================================"
echo ""
echo "📋 Service Management Commands:"
echo ""
echo "  View logs:"
echo "    tail -f $PROJECT_ROOT/logs/slack_monitor_stdout.log"
echo ""
echo "  Stop service:"
echo "    launchctl unload $PLIST_INSTALL"
echo ""
echo "  Start service:"
echo "    launchctl load $PLIST_INSTALL"
echo ""
echo "  Check status:"
echo "    launchctl list | grep $SERVICE_NAME"
echo ""
echo "  View recent output:"
echo "    tail -20 $PROJECT_ROOT/logs/slack_monitor_stdout.log"
echo ""
echo "📂 Tasks will be written to:"
echo "   $VAULT_PATH/00_Inbox/Slack/YYYY-MM-DD - Slack Captures.md"
echo ""
