#!/usr/bin/env -S uv run --quiet python
# /// script
# dependencies = [
#   "pychrome",
# ]
# ///
"""
Test actual message extraction from Slack.

This script tests if we can extract message content, author, and timestamp.
"""

import sys

try:
    import pychrome
except ImportError:
    print("❌ pychrome not installed")
    sys.exit(1)


def test_message_extraction():
    print("=" * 70)
    print("💬 Testing Slack Message Extraction")
    print("=" * 70)

    # Connect
    browser = pychrome.Browser(url="http://127.0.0.1:9222")
    tabs = browser.list_tab()
    tab = tabs[0]
    tab.start()

    print("\n✅ Connected to Slack\n")

    # Test: Extract actual message data
    print("📝 Extracting messages from current view...")
    print("-" * 70)

    result = tab.Runtime.evaluate(
        expression="""
        (() => {
            const messages = [];

            // Strategy 1: Find the message pane
            const messagePane = document.querySelector('.p-message_pane') ||
                               document.querySelector('.c-message_list');

            if (!messagePane) {
                return { error: 'Message pane not found' };
            }

            // Strategy 2: Find all elements with timestamps (indicates messages)
            const timePattern = /\\d{1,2}:\\d{2}\\s*(AM|PM)?/i;
            const allElements = messagePane.querySelectorAll('*');

            const messageContainers = new Set();

            allElements.forEach(el => {
                const text = el.innerText || '';
                if (timePattern.test(text) && text.length < 100) {
                    // Found a timestamp, walk up to find message container
                    let parent = el.parentElement;
                    for (let i = 0; i < 5 && parent; i++) {
                        const parentText = parent.innerText || '';

                        // Message container heuristics:
                        // - Has reasonable text length
                        // - Contains timestamp
                        // - Not too large (not the whole list)
                        if (parentText.length > 20 &&
                            parentText.length < 2000 &&
                            timePattern.test(parentText)) {

                            // Try to extract message components
                            const message = {
                                fullText: parentText,
                                timestamp: text.match(timePattern)?.[0],
                                classes: parent.className,
                                tag: parent.tagName
                            };

                            // Try to find author (usually before timestamp)
                            const lines = parentText.split('\\n');
                            if (lines.length > 1) {
                                message.possibleAuthor = lines[0];
                                message.possibleContent = lines.slice(2).join(' ').substring(0, 200);
                            }

                            messages.push(message);
                            break;
                        }
                        parent = parent.parentElement;
                    }
                }
            });

            // Deduplicate by full text
            const seen = new Set();
            const unique = messages.filter(msg => {
                const key = msg.fullText.substring(0, 100);
                if (seen.has(key)) return false;
                seen.add(key);
                return true;
            });

            return {
                found: unique.length,
                messages: unique.slice(0, 5)  // Return first 5
            };
        })()
        """,
        returnByValue=True,
    )

    data = result.get("result", {}).get("value", {})

    if data.get("error"):
        print(f"❌ {data['error']}")
        print("\n💡 Make sure you're viewing a channel with messages")
        tab.stop()
        return

    found = data.get("found", 0)
    messages = data.get("messages", [])

    if found == 0:
        print("❌ No messages found")
        print("\n💡 Possible issues:")
        print("   • Not viewing a channel with messages")
        print("   • Messages haven't loaded yet")
        print("   • DOM structure has changed")
        tab.stop()
        return

    print(f"✅ Found {found} message(s)!\n")
    print("Sample messages:")
    print("=" * 70)

    for i, msg in enumerate(messages, 1):
        print(f"\n📨 Message {i}:")
        print(f"   Timestamp: {msg.get('timestamp', 'N/A')}")
        print(f"   Author: {msg.get('possibleAuthor', 'N/A')}")
        print(f"   Content preview: {msg.get('possibleContent', 'N/A')[:150]}...")
        print(f"   Container: <{msg.get('tag')}> .{msg.get('classes', '').split()[0]}")

    # Now test if we can monitor for new messages
    print("\n" + "=" * 70)
    print("🔄 Testing real-time message monitoring...")
    print("=" * 70)

    result = tab.Runtime.evaluate(
        expression="""
        (() => {
            // Set up a mutation observer to detect new messages
            const messagePane = document.querySelector('.p-message_pane') ||
                               document.querySelector('.c-message_list');

            if (!messagePane) {
                return { error: 'Message pane not found' };
            }

            // Create observer
            window.__slackMessageObserver = new MutationObserver((mutations) => {
                // In production, this would trigger message extraction
                console.log('DOM changed - potential new message');
            });

            // Start observing
            window.__slackMessageObserver.observe(messagePane, {
                childList: true,
                subtree: true
            });

            return {
                observing: true,
                target: messagePane.className
            };
        })()
        """,
        returnByValue=True,
    )

    observer_data = result.get("result", {}).get("value", {})

    if observer_data.get("observing"):
        print("✅ MutationObserver set up successfully!")
        print(f"   Watching: .{observer_data.get('target', '').split()[0]}")
        print("\n💡 In production, this observer would:")
        print("   1. Detect when new messages arrive")
        print("   2. Extract message content")
        print("   3. Send to LLM for task detection")
        print("   4. Write tasks to Obsidian")
    else:
        print("❌ Could not set up observer")

    # Summary
    print("\n" + "=" * 70)
    print("📋 Summary")
    print("=" * 70)

    if found > 0:
        print("\n✅ SUCCESS: Can extract messages from Slack via CDP!")
        print(f"   • Found {found} messages in current view")
        print("   • Can set up real-time monitoring")
        print("   • Ready to build production monitor")

        print("\n💡 Next Steps:")
        print("   1. Build slack_cdp_monitor.py")
        print("   2. Extract messages every 30-60 seconds")
        print("   3. Use LLM to detect tasks (reuse from Phase 1)")
        print("   4. Write to Obsidian daily notes")
        print("   5. Deploy as launchd service")
    else:
        print("\n⚠️  CDP works but message extraction needs refinement")
        print("   • Try viewing a different channel")
        print("   • Make sure messages are visible")
        print("   • May need manual DevTools inspection")

    tab.stop()
    print("\n🔌 Disconnected\n")


if __name__ == "__main__":
    try:
        test_message_extraction()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
