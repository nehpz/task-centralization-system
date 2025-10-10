#!/usr/bin/env -S uv run --quiet python
# /// script
# dependencies = [
#   "pychrome",
# ]
# ///
"""
Inspect what's currently visible in Slack

Helps diagnose what we're actually looking at.
"""

import sys

try:
    import pychrome
except ImportError:
    print("❌ pychrome not installed")
    sys.exit(1)


def inspect_current_view():
    print("🔍 Inspecting current Slack view...")

    # Connect
    browser = pychrome.Browser(url="http://127.0.0.1:9222")
    tabs = browser.list_tab()
    tab = tabs[0]
    tab.start()

    # Get current URL and title
    result = tab.Runtime.evaluate(
        expression="""
        ({
            url: window.location.href,
            title: document.title,
            bodyText: document.body.innerText.substring(0, 500)
        })
        """,
        returnByValue=True,
    )

    info = result.get("result", {}).get("value", {})
    print("\n📄 Current Page:")
    print(f"   URL: {info['url']}")
    print(f"   Title: {info['title']}")
    print("\n📝 Visible text (first 500 chars):")
    print(f"   {info['bodyText'][:500]}")

    # Try to access message container specifically
    print("\n\n🎯 Looking for main message container...")

    result = tab.Runtime.evaluate(
        expression="""
        (() => {
            // Try multiple approaches to find messages
            const searches = {
                'Main content area': document.querySelector('[role="main"]'),
                'Message list': document.querySelector('[aria-label*="Message list"]'),
                'Virtual list': document.querySelector('.c-virtual_list__scroll_container'),
                'Any data-qa with message': document.querySelector('[data-qa^="message"]'),
                'Slack client view': document.querySelector('.p-client_container'),
            };

            const results = {};

            for (const [name, element] of Object.entries(searches)) {
                if (element) {
                    const text = element.innerText || '';
                    results[name] = {
                        found: true,
                        textLength: text.length,
                        preview: text.substring(0, 200),
                        childrenCount: element.children.length,
                        tag: element.tagName,
                        classes: element.className
                    };
                } else {
                    results[name] = { found: false };
                }
            }

            return results;
        })()
        """,
        returnByValue=True,
    )

    searches = result.get("result", {}).get("value", {})

    for name, data in searches.items():
        print(f"\n   {name}:")
        if data.get("found"):
            print("      ✅ Found!")
            print(f"      Tag: <{data['tag']}>")
            print(f"      Children: {data['childrenCount']}")
            print(f"      Text: {data['preview'][:100]}...")
        else:
            print("      ❌ Not found")

    # Check Redux store more thoroughly
    print("\n\n🔍 Deep Redux store check...")

    result = tab.Runtime.evaluate(
        expression="""
        (() => {
            const checks = {
                'window.TS exists': !!window.TS,
                'window.TS.redux exists': !!(window.TS && window.TS.redux),
                'window.TS.redux.store exists': !!(window.TS && window.TS.redux && window.TS.redux.store),
            };

            if (window.TS && window.TS.redux && window.TS.redux.store) {
                try {
                    const state = window.TS.redux.store.getState();
                    checks['State accessible'] = true;
                    checks['State keys'] = Object.keys(state).join(', ');
                } catch (e) {
                    checks['State accessible'] = false;
                    checks['Error'] = e.message;
                }
            }

            return checks;
        })()
        """,
        returnByValue=True,
    )

    redux_checks = result.get("result", {}).get("value", {})

    for check, value in redux_checks.items():
        if isinstance(value, bool):
            print(f"   {check}: {'✅ Yes' if value else '❌ No'}")
        else:
            print(f"   {check}: {value}")

    tab.stop()
    print("\n✅ Done\n")


if __name__ == "__main__":
    try:
        inspect_current_view()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
