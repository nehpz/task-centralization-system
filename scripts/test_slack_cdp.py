#!/usr/bin/env -S uv run --quiet python
# /// script
# dependencies = [
#   "pychrome",
# ]
# ///
"""
Slack CDP Test Script

Tests if we can access Slack messages via Chrome DevTools Protocol
while the app is running in the background (not necessarily visible).

Usage:
    1. Launch Slack with remote debugging:
       /Applications/Slack.app/Contents/MacOS/Slack --remote-debugging-port=9222 &

    2. Run this script:
       ./scripts/test_slack_cdp.py

    3. Minimize/background Slack to test visibility independence
"""

import sys
from typing import Any

try:
    import pychrome
except ImportError:
    print("❌ pychrome not installed")
    print("Install with: pip install pychrome")
    sys.exit(1)


class SlackCDPTester:
    """Test Chrome DevTools Protocol access to Slack"""

    def __init__(self, port: int = 9222):
        """
        Initialize CDP connection

        Args:
            port: Remote debugging port (default: 9222)
        """
        self.port = port
        self.browser: Any | None = None
        self.tab: Any | None = None

    def connect(self):
        """Connect to Slack's CDP endpoint"""
        print(f"🔌 Connecting to Slack CDP on port {self.port}...")
        try:
            # Connect to browser
            self.browser = pychrome.Browser(url=f"http://127.0.0.1:{self.port}")

            # Get list of tabs
            tabs = self.browser.list_tab()
            if not tabs:
                print("❌ No tabs found")
                return False

            # Just use the first available tab (Slack app should only have one)
            self.tab = tabs[0]
            self.tab.start()

            print(f"✅ Connected to Slack! (Tab ID: {self.tab.id})")
            return True

        except ConnectionRefusedError:
            print("❌ Connection refused")
            print("\nMake sure Slack is running with remote debugging:")
            print("/Applications/Slack.app/Contents/MacOS/Slack --remote-debugging-port=9222")
            return False
        except Exception as e:
            print(f"❌ Connection error: {e}")
            import traceback

            traceback.print_exc()
            return False

    def test_basic_dom_access(self):
        """Test 1: Can we access Slack's DOM?"""
        print("\n📋 Test 1: Basic DOM Access")
        print("-" * 50)

        if self.tab is None:
            print("❌ Not connected to CDP")
            return False

        try:
            result = self.tab.Runtime.evaluate(
                expression="""
                ({
                    url: window.location.href,
                    title: document.title,
                    bodyText: document.body ? document.body.innerText.substring(0, 100) : 'No body'
                })
            """,
                returnByValue=True,
            )

            data = result.get("result", {}).get("value", {})
            print(f"✅ URL: {data.get('url', 'N/A')}")
            print(f"✅ Title: {data.get('title', 'N/A')}")
            print(f"✅ Body preview: {data.get('bodyText', 'N/A')[:100]}...")
            return True

        except Exception as e:
            print(f"❌ Failed: {e}")
            import traceback

            traceback.print_exc()
            return False

    def test_slack_messages(self):
        """Test 2: Can we read Slack messages from the DOM?"""
        print("\n💬 Test 2: Message Reading")
        print("-" * 50)

        if self.tab is None:
            print("❌ Not connected to CDP")
            return False

        try:
            # Try multiple selectors (updated from DOM inspection 2025-10-09)
            selectors = [
                ".c-message_list",  # Main message list container
                ".c-message_kit__gutter__right",  # Message metadata (user, timestamp)
                ".c-message__reply_bar",  # Thread replies
                ".p-message_pane",  # Message pane container
                ".c-virtual_list__item",  # Virtual list items (sidebar)
                ".c-message_kit__background",  # Message containers
            ]

            for selector in selectors:
                print(f"\n🔍 Trying selector: {selector}")

                result = self.tab.Runtime.evaluate(
                    expression=f"""
                    {{
                        selector: '{selector}',
                        count: document.querySelectorAll('{selector}').length,
                        sample: Array.from(document.querySelectorAll('{selector}'))
                            .slice(0, 3)
                            .map(el => ({{
                                text: el.innerText.substring(0, 100),
                                classes: el.className
                            }}))
                    }}
                """,
                    returnByValue=True,
                )

                data = result.get("result", {}).get("value", {})
                count = data.get("count", 0)
                sample = data.get("sample", [])

                if count > 0:
                    print(f"✅ Found {count} elements!")
                    print("\nSample messages:")
                    for i, msg in enumerate(sample, 1):
                        text = msg.get("text", "").strip()[:100]
                        print(f"  {i}. {text}...")
                    return True

                print("⚠️  No elements found with this selector")

            print("\n❌ Could not find messages with any selector")
            print("💡 This might mean:")
            print("   - You need to navigate to a channel first")
            print("   - Slack is using a different DOM structure")
            print("   - Messages are loaded dynamically")
            return False

        except Exception as e:
            print(f"❌ Failed: {e}")
            import traceback

            traceback.print_exc()
            return False

    def run_all_tests(self):
        """Run all tests in sequence"""
        print("\n" + "=" * 50)
        print("🧪 Slack CDP Access Test Suite")
        print("=" * 50)

        if not self.connect():
            return

        results = {
            "DOM Access": self.test_basic_dom_access(),
            "Message Reading": self.test_slack_messages(),
        }

        # Summary
        print("\n" + "=" * 50)
        print("📊 Test Summary")
        print("=" * 50)

        for test, passed in results.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"{status} - {test}")

        total_passed = sum(results.values())
        total_tests = len(results)
        print(f"\nPassed: {total_passed}/{total_tests}")

        # Recommendations
        print("\n" + "=" * 50)
        print("💡 Next Steps")
        print("=" * 50)

        if results["DOM Access"] and results["Message Reading"]:
            print("✅ CDP access works! You can read Slack messages.")
            print("\nRecommended approach:")
            print("1. Use DOM selectors to extract messages")
            print("2. Poll every 5-30 seconds for new messages")
            print("3. Filter for task-creating messages")
            print("4. Process with LLM (reuse from Phase 1)")
        elif results["DOM Access"]:
            print("⚠️  DOM access works but message selectors need refinement")
            print("\nNext steps:")
            print("1. Navigate to a Slack channel manually")
            print("2. Open Chrome DevTools (Cmd+Option+I in Slack)")
            print("3. Find the correct message container selectors")
            print("4. Update this script with correct selectors")
        else:
            print("❌ CDP access not working as expected")
            print("\nTroubleshooting:")
            print("1. Verify Slack was launched with --remote-debugging-port=9222")
            print("2. Check if port 9222 is available (not used by another app)")
            print("3. Try restarting Slack with the debug flag")

        # Close connection
        if self.tab:
            self.tab.stop()
            print("\n🔌 Disconnected from CDP")


def main():
    """Main entry point"""
    tester = SlackCDPTester()
    tester.run_all_tests()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏸️  Test interrupted")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
