#!/usr/bin/env -S uv run --quiet python
# /// script
# dependencies = [
#   "pychrome",
# ]
# ///
"""
Find the actual message conversation area in Slack.

This script helps locate where messages are rendered.
"""

import sys

try:
    import pychrome
except ImportError:
    print("❌ pychrome not installed")
    sys.exit(1)


def find_message_area():
    print("=" * 70)
    print("🎯 Finding Slack Message Conversation Area")
    print("=" * 70)

    # Connect
    browser = pychrome.Browser(url="http://127.0.0.1:9222")
    tabs = browser.list_tab()
    tab = tabs[0]
    tab.start()

    print("\n1️⃣  Searching for conversation container...")
    print("-" * 70)

    # Look for conversation-specific containers
    result = tab.Runtime.evaluate(
        expression="""
        (() => {
            const candidates = [
                // Modern Slack selectors (2024-2025)
                '.p-workspace__primary_view',
                '.p-view_contents',
                '.p-message_pane',
                '.p-channel_sidebar__channel_scrollbar',
                '[data-qa="slack_kit_scrollbar"]',
                '[data-qa="channel_view_messages"]',
                '[data-qa="slack_kit_list"]',

                // Older selectors (might still work)
                '.c-scrollbar__hider',
                '.c-message_list',
                '.c-message_list__day_divider',
            ];

            const found = [];

            for (const selector of candidates) {
                const el = document.querySelector(selector);
                if (el) {
                    const text = el.innerText || '';
                    const hasSubstantialContent = text.length > 100;

                    found.push({
                        selector: selector,
                        textLength: text.length,
                        preview: text.substring(0, 150),
                        childCount: el.children.length,
                        className: el.className,
                        hasSubstantialContent: hasSubstantialContent
                    });
                }
            }

            return found;
        })()
        """,
        returnByValue=True,
    )

    containers = result.get("result", {}).get("value", [])

    if containers:
        print(f"✅ Found {len(containers)} potential containers:\n")
        for item in containers:
            print(f"   {item['selector']}")
            print(f"      Text length: {item['textLength']} chars")
            print(f"      Children: {item['childCount']}")
            print(f"      Content: {item['preview'][:100]}...")
            print()
    else:
        print("❌ No conversation containers found")

    print("\n2️⃣  Searching for any element with timestamp pattern...")
    print("-" * 70)

    # Messages typically have timestamps
    result = tab.Runtime.evaluate(
        expression="""
        (() => {
            // Look for elements with time patterns (HH:MM AM/PM or timestamps)
            const timePattern = /\\d{1,2}:\\d{2}\\s*(AM|PM)?/i;
            const timestampElements = [];

            document.querySelectorAll('*').forEach(el => {
                const text = el.innerText || '';
                if (timePattern.test(text) && text.length < 100) {
                    // Get the parent that might be the message container
                    let parent = el.parentElement;
                    for (let i = 0; i < 3 && parent; i++) {
                        const parentText = parent.innerText || '';
                        if (parentText.length > 20 && parentText.length < 2000) {
                            timestampElements.push({
                                timeText: text.substring(0, 30),
                                parentTag: parent.tagName,
                                parentClasses: parent.className.split(' ').slice(0, 3).join(' '),
                                parentText: parentText.substring(0, 100),
                                selector: parent.className.split(' ')[0] ? '.' + parent.className.split(' ')[0] : parent.tagName
                            });
                            break;
                        }
                        parent = parent.parentElement;
                    }
                }
            });

            // Return unique parent containers
            const seen = new Set();
            const unique = [];
            for (const item of timestampElements) {
                const key = item.selector;
                if (!seen.has(key)) {
                    seen.add(key);
                    unique.push(item);
                }
            }

            return unique.slice(0, 5);
        })()
        """,
        returnByValue=True,
    )

    timestamp_parents = result.get("result", {}).get("value", [])

    if timestamp_parents:
        print(f"✅ Found {len(timestamp_parents)} elements with timestamps:\n")
        for item in timestamp_parents:
            print(f"   Time: {item['timeText']}")
            print(f"   Parent: <{item['parentTag']}> {item['selector']}")
            print(f"   Classes: {item['parentClasses']}")
            print(f"   Text: {item['parentText']}...")
            print()
    else:
        print("❌ No timestamps found (messages might not be visible)")

    print("\n3️⃣  Comprehensive DOM structure analysis...")
    print("-" * 70)

    # Get a tree view of the main structure
    result = tab.Runtime.evaluate(
        expression="""
        (() => {
            const body = document.body;
            const structure = [];

            // Walk top-level structure
            const walk = (el, depth = 0, maxDepth = 4) => {
                if (depth > maxDepth) return;

                const text = el.innerText || '';
                const id = el.id || '';
                const classes = el.className.split(' ').filter(c => c).slice(0, 2).join(' ');
                const childCount = el.children.length;

                if (childCount > 0 || text.length > 50) {
                    structure.push({
                        depth: depth,
                        tag: el.tagName,
                        id: id,
                        classes: classes,
                        childCount: childCount,
                        textLength: text.length,
                        preview: text.substring(0, 60)
                    });

                    // Recurse on children
                    for (let i = 0; i < Math.min(el.children.length, 5); i++) {
                        walk(el.children[i], depth + 1, maxDepth);
                    }
                }
            };

            walk(body);
            return structure.slice(0, 30);
        })()
        """,
        returnByValue=True,
    )

    structure = result.get("result", {}).get("value", [])

    if structure:
        print("✅ DOM structure:\n")
        for item in structure:
            indent = "   " * item["depth"]
            id_str = f"#{item['id']}" if item["id"] else ""
            class_str = f".{item['classes']}" if item["classes"] else ""
            print(f"{indent}<{item['tag']}>{id_str}{class_str}")
            print(f"{indent}  ↳ {item['childCount']} children, {item['textLength']} chars")
            if item["preview"]:
                print(f'{indent}  ↳ "{item["preview"]}..."')
    else:
        print("❌ Couldn't analyze structure")

    print("\n" + "=" * 70)
    print("💡 Recommendations")
    print("=" * 70)

    if timestamp_parents:
        print("\n✅ Found message-like content!")
        print("   Try these selectors for messages:")
        for item in timestamp_parents[:3]:
            print(f"      {item['selector']}")
    elif containers:
        print("\n⚠️  Found containers but no messages")
        print("   Possible issues:")
        print("   • Messages not currently visible in Slack window")
        print("   • Slack is showing a different view (not a channel)")
        print("   • Need to scroll to load messages")
    else:
        print("\n❌ No message area detected")
        print("   Next steps:")
        print("   1. Make sure Slack window shows a channel with messages")
        print("   2. Make sure messages are visible (scroll if needed)")
        print("   3. Try clicking into a channel with recent activity")
        print("   4. Re-run this script")

    tab.stop()
    print()


if __name__ == "__main__":
    try:
        find_message_area()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
