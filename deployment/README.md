# Slack CDP Monitor Deployment

This directory contains configuration and documentation for deploying the Slack CDP Monitor as a background service on macOS.

## Overview

The Slack CDP Monitor runs as a macOS launchd service that:
- Monitors Slack messages via Chrome DevTools Protocol
- Extracts task-creating messages using LLM (Perplexity)
- Writes structured tasks to Obsidian daily notes
- Runs continuously in the background

## Prerequisites

1. **Slack running with CDP enabled**
   ```bash
   ./scripts/start_slack_with_cdp.sh
   ```

2. **PERPLEXITY_API_KEY set in environment**
   ```bash
   export PERPLEXITY_API_KEY='your-key-here'
   ```

   Add to `~/.zshrc` or `~/.bashrc` for persistence

3. **uv package manager installed**
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

## Quick Start

### 1. Deploy the Service

```bash
cd ~/Projects/rzp-labs/task-centralization-system
./scripts/deploy_slack_monitor.sh
```

This script will:
- Check all prerequisites
- Create the launchd plist with your API key
- Install the service to `~/Library/LaunchAgents/`
- Load and start the service
- Show service status

### 2. Verify It's Running

```bash
# Check service status
launchctl list | grep com.rzp.slack-monitor

# View live logs
tail -f logs/slack_monitor_stdout.log
```

### 3. Check for Tasks

Tasks are written to:
```
~/Obsidian/zenyth/00_Inbox/Slack/YYYY-MM-DD - Slack Captures.md
```

## Service Management

### Stop the Service

```bash
launchctl unload ~/Library/LaunchAgents/com.rzp.slack-monitor.plist
```

### Start the Service

```bash
launchctl load ~/Library/LaunchAgents/com.rzp.slack-monitor.plist
```

### Restart the Service

```bash
launchctl unload ~/Library/LaunchAgents/com.rzp.slack-monitor.plist
launchctl load ~/Library/LaunchAgents/com.rzp.slack-monitor.plist
```

### View Logs

**Live monitoring:**
```bash
tail -f ~/Projects/rzp-labs/task-centralization-system/logs/slack_monitor_stdout.log
```

**Errors:**
```bash
tail -f ~/Projects/rzp-labs/task-centralization-system/logs/slack_monitor_stderr.log
```

**Recent activity:**
```bash
tail -50 ~/Projects/rzp-labs/task-centralization-system/logs/slack_monitor_stdout.log
```

### Check Process Status

```bash
# List service
launchctl list | grep com.rzp.slack-monitor

# Get PID
ps aux | grep slack_cdp_monitor
```

## Configuration

### Service Configuration File

Location: `~/Library/LaunchAgents/com.rzp.slack-monitor.plist`

Key settings:
- **Check interval**: 60 seconds (default)
- **Log location**: `logs/slack_monitor_stdout.log`
- **Vault path**: `~/Obsidian/zenyth`
- **Auto-restart**: Yes (on crashes)

### Customize Check Interval

Edit the plist and change the `--interval` argument:

```xml
<string>--interval</string>
<string>30</string>  <!-- Check every 30 seconds -->
```

Then reload:
```bash
launchctl unload ~/Library/LaunchAgents/com.rzp.slack-monitor.plist
launchctl load ~/Library/LaunchAgents/com.rzp.slack-monitor.plist
```

## Troubleshooting

### Service Won't Start

1. **Check logs for errors:**
   ```bash
   tail -50 logs/slack_monitor_stderr.log
   ```

2. **Verify Slack is running with CDP:**
   ```bash
   pgrep -f "Slack.*remote-debugging-port"
   ```

   If not, run:
   ```bash
   ./scripts/start_slack_with_cdp.sh
   ```

3. **Verify PERPLEXITY_API_KEY is set:**
   ```bash
   grep PERPLEXITY_API_KEY ~/Library/LaunchAgents/com.rzp.slack-monitor.plist
   ```

4. **Test manually:**
   ```bash
   uv run src/slack_cdp_monitor.py --vault ~/Obsidian/zenyth --max-iterations 1
   ```

### No Tasks Being Extracted

1. **Check if messages are being detected:**
   ```bash
   grep "Extracted.*messages" logs/slack_monitor_stdout.log | tail -5
   ```

2. **Check LLM calls:**
   ```bash
   grep "Extracting tasks" logs/slack_monitor_stdout.log | tail -5
   ```

3. **Verify Slack is active:**
   - Navigate to a channel with messages
   - The monitor only sees what's in the current view

### High CPU Usage

The monitor uses CDP to poll Slack's DOM. To reduce CPU:

1. **Increase check interval** (edit plist):
   ```xml
   <string>--interval</string>
   <string>120</string>  <!-- Check every 2 minutes -->
   ```

2. **Limit to specific channels** (future feature)

## Automatic Slack Startup

To ensure Slack always starts with CDP enabled on login:

### Option 1: Manual Startup Script

Add to your `~/.zshrc`:
```bash
# Start Slack with CDP on shell init (runs once per session)
if ! pgrep -f "Slack.*remote-debugging-port" >/dev/null; then
    /Applications/Slack.app/Contents/MacOS/Slack --remote-debugging-port=9222 &
fi
```

### Option 2: Login Item

1. Create launchd agent for Slack startup
2. Add to `~/Library/LaunchAgents/com.slack.cdp-startup.plist`

(This is optional and can be added later if needed)

## Files

- `com.rzp.slack-monitor.plist` - Service configuration template
- `README.md` - This file
- `../scripts/deploy_slack_monitor.sh` - Deployment script
- `../scripts/start_slack_with_cdp.sh` - Slack startup helper

## Monitoring and Maintenance

### Daily Checks

The service writes to daily notes automatically. Review:
```
~/Obsidian/zenyth/00_Inbox/Slack/
```

### Weekly Maintenance

1. Check log file sizes:
   ```bash
   du -sh logs/*.log
   ```

2. Rotate logs if needed:
   ```bash
   mv logs/slack_monitor_stdout.log logs/slack_monitor_stdout.log.old
   launchctl unload ~/Library/LaunchAgents/com.rzp.slack-monitor.plist
   launchctl load ~/Library/LaunchAgents/com.rzp.slack-monitor.plist
   ```

3. Review extracted tasks for quality

### Uninstall

To completely remove the service:

```bash
# Stop and unload
launchctl unload ~/Library/LaunchAgents/com.rzp.slack-monitor.plist

# Remove plist
rm ~/Library/LaunchAgents/com.rzp.slack-monitor.plist

# Optional: Remove logs
rm -rf ~/Projects/rzp-labs/task-centralization-system/logs/slack_monitor_*.log
```

## Security Notes

- The PERPLEXITY_API_KEY is stored in the plist file (readable only by your user)
- CDP access is local-only (port 9222 is not exposed to network)
- No Slack data leaves your machine except LLM API calls for task extraction
- Consider API key rotation periodically

## Performance

**Expected resource usage:**
- **CPU**: ~1-5% during checks, 0% idle
- **Memory**: ~100-200 MB
- **Network**: Minimal (only LLM API calls when tasks detected)
- **Disk**: Log files grow ~1 MB/day

## Support

For issues or questions:
1. Check logs first
2. Test manually with `--max-iterations 1`
3. Verify all prerequisites are met

---

**Last Updated**: 2025-10-09
**Version**: 1.0.0
