#!/usr/bin/env -S uv run --quiet python
# /// script
# dependencies = [
#   "pychrome",
# ]
# ///
"""
Slack DOM Inspector

Explores Slack's actual DOM structure to find message selectors.
Run this while viewing a channel with messages.

Usage:
    1. Launch Slack with debugging:
       /Applications/Slack.app/Contents/MacOS/Slack --remote-debugging-port=9222 &

    2. Navigate to a channel with messages

    3. Run this script:
       ./scripts/inspect_slack_dom.py
"""

import sys
from typing import Any

try:
    import pychrome
except ImportError:
    print("❌ pychrome not installed")
    sys.exit(1)


class SlackDOMInspector:
    """Inspect Slack's DOM to find message selectors"""

    def __init__(self, port: int = 9222):
        self.port = port
        self.browser: Any | None = None
        self.tab: Any | None = None

    def connect(self):
        """Connect to Slack"""
        print("🔌 Connecting to Slack...")
        try:
            self.browser = pychrome.Browser(url=f"http://127.0.0.1:{self.port}")
            tabs = self.browser.list_tab()

            if not tabs:
                print("❌ No tabs found")
                return False

            self.tab = tabs[0]
            self.tab.start()
            print("✅ Connected!")
            return True

        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False

    def find_all_message_classes(self):
        """Find all classes that might contain messages"""
        print("\n🔍 Searching for message-related classes...")
        print("-" * 60)

        assert self.tab is not None
        result = self.tab.Runtime.evaluate(
            expression="""
            (() => {
                // Get all elements with class names containing common message keywords
                const keywords = ['message', 'msg', 'chat', 'text', 'content', 'virtual', 'list', 'item'];
                const classesFound = new Set();

                // Search all elements
                document.querySelectorAll('*').forEach(el => {
                    if (el.className && typeof el.className === 'string') {
                        const classes = el.className.split(' ');
                        classes.forEach(cls => {
                            if (keywords.some(kw => cls.toLowerCase().includes(kw))) {
                                classesFound.add(cls);
                            }
                        });
                    }
                });

                return Array.from(classesFound).sort();
            })()
            """,
            returnByValue=True,
        )

        classes = result.get("result", {}).get("value", [])

        if classes:
            print(f"✅ Found {len(classes)} potentially relevant classes:")
            for cls in classes[:20]:  # Show first 20
                print(f"   .{cls}")
            if len(classes) > 20:
                print(f"   ... and {len(classes) - 20} more")
        else:
            print("❌ No message-related classes found")

        return classes

    def find_elements_with_text(self):
        """Find elements containing text content (likely messages)"""
        print("\n📝 Searching for elements with substantial text...")
        print("-" * 60)

        assert self.tab is not None
        result = self.tab.Runtime.evaluate(
            expression="""
            (() => {
                const elementsWithText = [];

                // Look for elements with significant text content
                document.querySelectorAll('*').forEach(el => {
                    const text = el.innerText || '';
                    const hasText = text.length > 20 && text.length < 500;

                    // Skip if it's the entire body or very nested
                    const isBody = el.tagName === 'BODY';
                    const depth = el.querySelectorAll('*').length;
                    const isContainer = depth > 10;

                    if (hasText && !isBody && !isContainer) {
                        // Get useful selectors
                        const selectors = [];

                        if (el.id) selectors.push('#' + el.id);
                        if (el.className) {
                            const classes = el.className.split(' ').filter(c => c);
                            if (classes.length > 0) {
                                selectors.push('.' + classes[0]);
                            }
                        }

                        const dataAttrs = Array.from(el.attributes)
                            .filter(attr => attr.name.startsWith('data-'))
                            .map(attr => `[${attr.name}]`);

                        selectors.push(...dataAttrs);

                        elementsWithText.push({
                            tag: el.tagName,
                            selectors: selectors,
                            textPreview: text.substring(0, 60),
                            childCount: el.children.length
                        });
                    }
                });

                // Return top 10
                return elementsWithText.slice(0, 10);
            })()
            """,
            returnByValue=True,
        )

        elements = result.get("result", {}).get("value", [])

        if elements:
            print(f"✅ Found {len(elements)} elements with text content:")
            for i, el in enumerate(elements, 1):
                print(f"\n   {i}. <{el['tag']}> ({el['childCount']} children)")
                print(f"      Selectors: {', '.join(el['selectors'][:3])}")
                print(f'      Text: "{el["textPreview"]}..."')
        else:
            print("❌ No elements with text found")

        return elements

    def test_selector(self, selector):
        """Test if a selector finds elements"""
        print(f"\n🧪 Testing: {selector}")

        assert self.tab is not None
        result = self.tab.Runtime.evaluate(
            expression=f"""
            (() => {{
                const elements = document.querySelectorAll('{selector}');
                const samples = Array.from(elements).slice(0, 3).map(el => ({{
                    text: el.innerText ? el.innerText.substring(0, 100) : '(no text)',
                    tag: el.tagName,
                    classes: el.className
                }}));

                return {{
                    count: elements.length,
                    samples: samples
                }};
            }})()
            """,
            returnByValue=True,
        )

        data = result.get("result", {}).get("value", {})
        count = data.get("count", 0)
        samples = data.get("samples", [])

        if count > 0:
            print(f"   ✅ Found {count} elements!")
            for i, sample in enumerate(samples, 1):
                print(f"      {i}. <{sample['tag']}> {sample['text'][:50]}...")
            return True
        print("   ❌ No elements found")
        return False

    def suggest_selectors(self, classes):
        """Try various selector combinations"""
        print("\n💡 Testing common selector patterns...")
        print("-" * 60)

        # Build test selectors from found classes
        test_selectors = []

        # Try message-specific classes
        message_classes = [c for c in classes if "message" in c.lower()]
        test_selectors.extend([f".{c}" for c in message_classes[:5]])

        # Try list/item classes
        list_classes = [
            c for c in classes if any(kw in c.lower() for kw in ["list", "item", "row"])
        ]
        test_selectors.extend([f".{c}" for c in list_classes[:5]])

        # Common data attributes
        test_selectors.extend(
            [
                '[data-qa*="message"]',
                '[data-qa*="item"]',
                '[role="listitem"]',
                '[role="article"]',
                '[aria-label*="message"]',
            ]
        )

        working_selectors = []
        for selector in test_selectors:
            if self.test_selector(selector):
                working_selectors.append(selector)

        return working_selectors

    def explore_slack_structure(self):
        """Main exploration function"""
        print("\n" + "=" * 60)
        print("🔬 Slack DOM Structure Explorer")
        print("=" * 60)

        if not self.connect():
            return

        # Step 1: Find all message-related classes
        classes = self.find_all_message_classes()

        # Step 2: Find elements with text (likely messages)
        elements = self.find_elements_with_text()

        # Step 3: Test and suggest working selectors
        working = self.suggest_selectors(classes)

        # Summary
        print("\n" + "=" * 60)
        print("📋 Summary & Recommendations")
        print("=" * 60)

        if working:
            print("\n✅ Working selectors found:")
            for selector in working:
                print(f"   {selector}")

            print("\n💡 Next steps:")
            print("   1. Update test_slack_cdp.py with these selectors")
            print("   2. Run the full test suite again")
            print("   3. Build the real-time monitor")
        else:
            print("\n⚠️  No working selectors found")
            print("\n💡 Manual inspection needed:")
            print("   1. Open Chrome DevTools in Slack (Cmd+Option+I)")
            print("   2. Use Elements tab to inspect a message")
            print("   3. Right-click → Copy → Copy selector")
            print("   4. Share the selector here")

            if elements:
                print("\n   These elements look promising:")
                for el in elements[:3]:
                    if el["selectors"]:
                        print(f"   - {el['selectors'][0]}")

        # Cleanup
        if self.tab:
            self.tab.stop()
            print("\n🔌 Disconnected")


def main():
    inspector = SlackDOMInspector()
    inspector.explore_slack_structure()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏸️  Interrupted")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
