#!/usr/bin/env -S uv run --quiet python
# /// script
# dependencies = [
#   "pychrome",
# ]
# ///
"""
Find Slack Message Selectors

Specifically targets the message content area.
Navigate to a channel with visible messages before running.

Usage:
    1. Ensure Slack is open to a channel with messages visible
    2. Run: ./scripts/find_slack_messages.py
"""

import sys

try:
    import pychrome
except ImportError:
    print("❌ pychrome not installed")
    sys.exit(1)


def find_message_selectors():
    """Find selectors specifically for message content"""
    print("\n" + "=" * 60)
    print("🔍 Finding Slack Message Content Selectors")
    print("=" * 60)

    # Connect to Slack
    print("\n🔌 Connecting to Slack...")
    try:
        browser = pychrome.Browser(url="http://127.0.0.1:9222")
        tabs = browser.list_tab()

        if not tabs:
            print("❌ No tabs found")
            return

        tab = tabs[0]
        tab.start()
        print("✅ Connected!")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return

    # Strategy 1: Look for elements with specific message indicators
    print("\n📝 Strategy 1: Looking for message-specific attributes...")
    print("-" * 60)

    result = tab.Runtime.evaluate(
        expression="""
        (() => {
            const results = [];

            // Common Slack message patterns
            const patterns = [
                '[data-qa="message_container"]',
                '[data-qa*="virtual_list_item"]',
                '[data-qa*="message"]',
                '[class*="c-message"]',
                '[class*="c-virtual_list__item"]',
                '[role="group"]',
                '[data-item-key]',
                '.c-message_kit__message',
                '.c-message_kit__background',
                '.p-rich_text_block',
                '.c-message__body',
                '.c-message__sender',
            ];

            for (const pattern of patterns) {
                const elements = document.querySelectorAll(pattern);
                if (elements.length > 0) {
                    // Get sample text from first few
                    const samples = Array.from(elements).slice(0, 3).map(el => ({
                        text: el.innerText?.substring(0, 100) || '(no text)',
                        tag: el.tagName,
                        hasTime: !!el.querySelector('[data-qa*="timestamp"]'),
                        hasAuthor: !!el.querySelector('[data-qa*="author"]'),
                    }));

                    results.push({
                        selector: pattern,
                        count: elements.length,
                        samples: samples
                    });
                }
            }

            return results;
        })()
        """,
        returnByValue=True,
    )

    message_selectors = result.get("result", {}).get("value", [])

    if message_selectors:
        print(f"✅ Found {len(message_selectors)} working patterns:\n")
        for item in message_selectors:
            print(f"   {item['selector']}")
            print(f"   → {item['count']} elements found")
            for i, sample in enumerate(item["samples"][:2], 1):
                print(f"      Sample {i}: {sample['text'][:60]}...")
                if sample["hasTime"]:
                    print("                 ✅ Has timestamp")
                if sample["hasAuthor"]:
                    print("                 ✅ Has author")
            print()
    else:
        print("❌ No message patterns found with Strategy 1")

    # Strategy 2: Look for repeating structure (messages have similar DOM)
    print("\n📝 Strategy 2: Finding repeating elements (message structure)...")
    print("-" * 60)

    result = tab.Runtime.evaluate(
        expression="""
        (() => {
            // Find elements that appear multiple times with similar structure
            const classCount = {};

            document.querySelectorAll('[class]').forEach(el => {
                const classList = el.className.split(' ');
                classList.forEach(cls => {
                    if (cls) {
                        classCount[cls] = (classCount[cls] || 0) + 1;
                    }
                });
            });

            // Get classes that appear 5+ times (likely message containers)
            const repeating = Object.entries(classCount)
                .filter(([cls, count]) => count >= 5 && count <= 200)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 10);

            // Test each one to see if it looks like messages
            const messageCandidates = [];

            for (const [cls, count] of repeating) {
                const elements = document.querySelectorAll('.' + cls);
                const first = elements[0];

                if (first) {
                    const text = first.innerText || '';
                    const hasReasonableText = text.length > 10 && text.length < 1000;

                    // Check if it has message-like children
                    const hasTextBlock = !!first.querySelector('[class*="text"], [class*="message"]');

                    if (hasReasonableText || hasTextBlock) {
                        messageCandidates.push({
                            selector: '.' + cls,
                            count: count,
                            textPreview: text.substring(0, 80),
                            hasTextBlock: hasTextBlock
                        });
                    }
                }
            }

            return messageCandidates;
        })()
        """,
        returnByValue=True,
    )

    candidates = result.get("result", {}).get("value", [])

    if candidates:
        print(f"✅ Found {len(candidates)} potential message container patterns:\n")
        for item in candidates:
            print(f"   {item['selector']}")
            print(f"   → {item['count']} instances")
            print(f"   → Text: {item['textPreview']}")
            if item["hasTextBlock"]:
                print("   → ✅ Contains text/message block")
            print()
    else:
        print("❌ No repeating patterns found")

    # Strategy 3: Look for Redux store
    print("\n📝 Strategy 3: Checking for Slack Redux store...")
    print("-" * 60)

    result = tab.Runtime.evaluate(
        expression="""
        (() => {
            if (window.TS && window.TS.redux && window.TS.redux.store) {
                const state = window.TS.redux.store.getState();

                return {
                    hasRedux: true,
                    stateKeys: Object.keys(state).slice(0, 20),
                    hasMessages: !!state.messages,
                };
            }

            return { hasRedux: false };
        })()
        """,
        returnByValue=True,
    )

    redux_info = result.get("result", {}).get("value", {})

    if redux_info.get("hasRedux"):
        print("✅ Redux store found!")
        print(f"   State keys: {', '.join(redux_info['stateKeys'])}")
        if redux_info.get("hasMessages"):
            print("   ✅ Has messages in state!")
            print("\n   💡 Alternative approach: Access messages via Redux store")
            print("      window.TS.redux.store.getState().messages")
    else:
        print("❌ Redux store not accessible")

    # Summary
    print("\n" + "=" * 60)
    print("📋 Summary & Recommendations")
    print("=" * 60)

    best_selectors = [item["selector"] for item in message_selectors if item["count"] > 0]

    if best_selectors:
        print("\n✅ WORKING MESSAGE SELECTORS:")
        for selector in best_selectors[:5]:
            print(f"   {selector}")

        print("\n💡 Next step:")
        print("   Update test_slack_cdp.py MESSAGE_SELECTORS with these values")
    else:
        print("\n⚠️  No clear message selectors found automatically")
        print("\n💡 Manual inspection required:")
        print("   1. In Slack, right-click on a message")
        print("   2. Choose 'Inspect Element' (or press Cmd+Option+I)")
        print("   3. Find the containing div for the message")
        print("   4. Look for data-qa or class attributes")
        print("   5. Share the selector pattern")

    if redux_info.get("hasRedux"):
        print("\n✅ ALTERNATIVE: Use Redux store")
        print("   Access messages directly via JavaScript:")
        print("   window.TS.redux.store.getState().messages")

    # Cleanup
    tab.stop()
    print("\n🔌 Disconnected\n")


if __name__ == "__main__":
    try:
        find_message_selectors()
    except KeyboardInterrupt:
        print("\n\n⏸️  Interrupted")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
