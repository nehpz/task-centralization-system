# Slack CDP Access Test

**Purpose**: Test if we can capture Slack messages via Chrome DevTools Protocol without using the Slack API.

**Approach**: Host-based data collection using privileged access to the Slack Electron app.

---

## Quick Start

### Step 1: Install Dependencies

```bash
cd ~/Projects/rzp-labs/task-centralization-system
uv pip install pycdp
```

Or add to `pyproject.toml` dependencies (recommended):
```bash
uv add pycdp
```

### Step 2: Launch Slack with Remote Debugging

**Important**: You need to quit Slack first, then launch it with the debug flag.

```bash
# Quit Slack if running
killall Slack

# Launch with remote debugging enabled
/Applications/Slack.app/Contents/MacOS/Slack --remote-debugging-port=9222 &
```

**What this does**:
- Launches Slack with Chrome DevTools Protocol enabled
- Allows external programs to inspect and control the app
- Port 9222 is the standard debugging port

### Step 3: Navigate to a Channel

**In Slack**:
1. Open Slack (it should be running from step 2)
2. Navigate to any channel with messages
3. You can minimize Slack - it doesn't need to be visible!

### Step 4: Run the Test

```bash
./scripts/test_slack_cdp.py
```

**What it tests**:
1. ✅ Can we connect to Slack's CDP?
2. ✅ Can we read the DOM (page structure)?
3. ✅ Can we extract messages from the page?
4. ✅ Can we access Slack's internal Redux store?
5. ✅ Can we monitor network requests (to extract API tokens)?

---

## Expected Output

### Success Case

```
🧪 Slack CDP Access Test Suite
==================================================

🔌 Connecting to Slack CDP on port 9222...
✅ Connected to Slack!

📋 Test 1: Basic DOM Access
--------------------------------------------------
✅ URL: https://app.slack.com/client/T01ABC123/C01DEF456
✅ Title: #general | Your Workspace
✅ Body preview: #general
  Stephen Mangrum 2:30 PM
  Hey team, can you review...

💬 Test 2: Message Reading
--------------------------------------------------
🔍 Trying selector: .c-virtual_list__item
✅ Found 47 elements!

Sample messages:
  1. Stephen Mangrum 2:30 PM
     Hey team, can you review the design doc by Friday?...
  2. Jane Doe 2:35 PM
     Sure, I'll take a look this afternoon...
  3. John Smith 2:40 PM
     @stephen Added some comments, looks good overall...

🏪 Test 3: Redux Store Access
--------------------------------------------------
✅ window.TS exists (Slack's global object)
✅ window.TS.redux exists
✅ window.TS.redux.store exists

📊 Redux state keys (first 10):
   - messages
   - channels
   - users
   - teams
   - ...

🌐 Test 4: Network Monitoring
--------------------------------------------------
✅ Network monitoring enabled

⏳ Monitoring network requests for 5 seconds...
   (Try sending a message in Slack)

✅ Captured 3 Slack API calls:
   1. POST https://edgeapi.slack.com/cache/...
   2. GET https://slack.com/api/conversations.history...
   3. POST https://slack.com/api/chat.postMessage...

==================================================
📊 Test Summary
==================================================
✅ PASS - DOM Access
✅ PASS - Message Reading
✅ PASS - Redux Store
✅ PASS - Network Monitoring

Passed: 4/4

==================================================
💡 Next Steps
==================================================
✅ CDP access works! You can read Slack messages.

Recommended approach:
1. Use DOM selectors to extract messages
2. Poll every 5-30 seconds for new messages
3. Filter for task-creating messages
4. Process with LLM (reuse from Phase 1)
```

### Failure Cases

**If Slack not launched with debug flag**:
```
❌ Connection refused

Make sure Slack is running with remote debugging:
/Applications/Slack.app/Contents/MacOS/Slack --remote-debugging-port=9222
```

**If message selectors don't match**:
```
⚠️  No elements found with this selector

💡 This might mean:
   - You need to navigate to a channel first
   - Slack is using a different DOM structure
   - Messages are loaded dynamically
```

---

## What This Proves

### If Tests Pass

**You can capture Slack messages without**:
- ❌ Slack API authentication
- ❌ Admin approval for app installation
- ❌ Browser session token extraction
- ❌ Network calls (IT monitoring)
- ❌ Slack app needing to be visible/focused

**Requirements**:
- ✅ Slack running (can be minimized/background)
- ✅ One-time launch with debug flag
- ✅ Host privileges (it's your computer)

### Comparison to API Approach

| Aspect | CDP (Host-Based) | API (Session Token) | API (Official) |
|--------|------------------|---------------------|----------------|
| Authentication | None | Browser token | Admin approval |
| Network traffic | None (local) | API calls (visible) | API calls |
| Rate limits | None | 50+ req/min | 50+ req/min |
| Coverage | Messages in active channels | All messages | All messages |
| Historical data | Only new messages | Full history | Full history |
| Slack running? | Yes (background OK) | No | No |

---

## Next Steps Based on Results

### If All Tests Pass ✅

**Build the real-time capture service**:
1. Create `slack_cdp_monitor.py` (similar to `granola_sync.py`)
2. Poll every 30 seconds for new messages
3. Filter for task-creating messages (keywords, @mentions)
4. Extract with LLM (reuse Phase 1 processor)
5. Write to Obsidian daily notes
6. Deploy as launchd service (auto-start on login)

**Timeline**: 1-2 weeks for full implementation

### If DOM Access Works But Message Reading Fails ⚠️

**Refine selectors**:
1. Open Slack with CDP debugging
2. Navigate to channel manually
3. Open Chrome DevTools in Slack: `Cmd+Option+I`
4. Inspect message elements
5. Find correct CSS selectors
6. Update test script

**Timeline**: 30 minutes to find correct selectors

### If Connection Fails ❌

**Troubleshooting**:
1. Verify Slack was quit before launching with debug flag
2. Check port 9222 isn't used: `lsof -i :9222`
3. Try different port: `--remote-debugging-port=9223`
4. Check Slack permissions in macOS Security & Privacy

---

## Making This Production-Ready

### Auto-launch Slack with Debug Flag

Create launchd plist to always start Slack with debugging:

**File**: `~/Library/LaunchAgents/com.user.slack.debug.plist`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.slack.debug</string>

    <key>ProgramArguments</key>
    <array>
        <string>/Applications/Slack.app/Contents/MacOS/Slack</string>
        <string>--remote-debugging-port=9222</string>
    </array>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
</dict>
</plist>
```

**Load it**:
```bash
launchctl load ~/Library/LaunchAgents/com.user.slack.debug.plist
```

**Result**: Slack always starts with CDP enabled after login

---

## Security Considerations

### Is This Safe?

**From a technical perspective**:
- ✅ You're only accessing your own local data
- ✅ No modification of Slack app
- ✅ No network interception
- ✅ Similar to screen recording permission

**From a policy perspective**:
- ⚠️ Still accessing Slack data without explicit consent
- ⚠️ Enterprise DLP might flag unusual process access
- ⚠️ Likely same legal risk as API session token method

**Recommendation**:
- Use for personal workspace: Probably fine
- Use for enterprise workspace: Check with IT/Legal first

### Can Slack Detect This?

**Unlikely for several reasons**:
- CDP is a standard Chromium debugging feature
- No modification to Slack's code
- All access is local (no network signatures)
- IT can only detect if they have endpoint monitoring (EDR)

**However**:
- Slack could add checks for `--remote-debugging-port` flag
- They could obfuscate Redux store to prevent access
- Enterprise endpoint security might flag the debug flag

---

## Comparison to Hoop's Approach

**Hoop for Meetings**:
- Uses microphone + system audio capture
- Transcribes audio with Deepgram
- Extracts tasks with LLM

**Hoop for Slack**:
- Uses official Slack API (requires OAuth)
- Full message history access
- No host-level access needed

**Our Approach**:
- Uses CDP to read Slack's DOM/state
- No API authentication
- Only works while Slack is running
- Hybrid between Hoop's methods

---

## Related Documentation

- [[Host-Based Slack Collection Architecture]] - Full architectural analysis
- [[Phase 2 - Integration Options Research]] - API vs. host-based comparison

---

**Created**: 2025-10-09
**Status**: Ready for testing
**Next**: Run the test and evaluate results
