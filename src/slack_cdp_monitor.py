#!/usr/bin/env -S uv run --quiet python
# /// script
# dependencies = [
#   "pychrome",
#   "openai",
#   "pyyaml",
# ]
# ///
"""
Slack CDP Monitor

Monitors Slack messages via Chrome DevTools Protocol and extracts task-creating messages.
Writes task captures to Obsidian daily notes.
"""

import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

try:
    import pychrome
except ImportError:
    logger.error("pychrome not installed. Install with: pip install pychrome")
    sys.exit(1)


class SlackCDPMonitor:
    """Monitor Slack messages via CDP and extract tasks"""

    def __init__(
        self,
        vault_path: str,
        enable_llm: bool = True,
        cdp_port: int = 9222,
        check_interval: int = 60,
    ):
        """
        Initialize Slack CDP monitor

        Args:
            vault_path: Path to Obsidian vault
            enable_llm: Enable LLM-based task extraction (default: True)
            cdp_port: Chrome DevTools Protocol port (default: 9222)
            check_interval: Seconds between message checks (default: 60)
        """
        self.vault_path = Path(vault_path)
        self.cdp_port = cdp_port
        self.check_interval = check_interval
        self.browser: Any | None = None
        self.tab: Any | None = None

        # State tracking
        self.last_check_time = datetime.now()
        self.seen_message_ids: set[str] = set()

        # Initialize LLM parser if enabled
        self.llm_parser = None
        if enable_llm:
            try:
                # Use openai client directly (Perplexity API)
                import os

                from openai import OpenAI

                api_key = os.getenv("PERPLEXITY_API_KEY")
                if not api_key:
                    logger.warning("PERPLEXITY_API_KEY not set. LLM enrichment disabled.")
                else:
                    # Create simple LLM client wrapper
                    class SimpleLLMClient:
                        def __init__(self, api_key: str, model: str = "sonar-pro"):
                            self.client = OpenAI(
                                api_key=api_key, base_url="https://api.perplexity.ai"
                            )
                            self.model = model

                    self.llm_parser = SimpleLLMClient(api_key)
                    logger.info(
                        "SlackCDPMonitor initialized with LLM enrichment (Perplexity sonar-pro)"
                    )
            except Exception as e:
                logger.warning(
                    f"LLM parser initialization failed: {e}. Continuing without LLM enrichment."
                )
        else:
            logger.info("SlackCDPMonitor initialized (LLM enrichment disabled)")

        logger.info(
            f"Monitor configured: vault={vault_path}, port={cdp_port}, interval={check_interval}s"
        )

    def connect(self) -> bool:
        """
        Connect to Slack via CDP

        Returns:
            True if connected successfully, False otherwise
        """
        logger.info(f"Connecting to Slack CDP on port {self.cdp_port}...")

        try:
            self.browser = pychrome.Browser(url=f"http://127.0.0.1:{self.cdp_port}")
            tabs = self.browser.list_tab()

            if not tabs:
                logger.error("No tabs found. Is Slack running with --remote-debugging-port?")
                return False

            self.tab = tabs[0]
            self.tab.start()

            logger.info(f"✅ Connected to Slack (Tab ID: {self.tab.id})")
            return True

        except ConnectionRefusedError:
            logger.error("Connection refused. Ensure Slack is running with:")
            logger.error(
                "/Applications/Slack.app/Contents/MacOS/Slack --remote-debugging-port=9222 &"
            )
            return False
        except Exception as e:
            logger.error(f"Connection error: {e}")
            return False

    def disconnect(self):
        """Disconnect from CDP"""
        if self.tab:
            self.tab.stop()
            logger.info("Disconnected from Slack CDP")

    def extract_messages(self) -> list[dict[str, Any]]:
        """
        Extract messages from current Slack view

        Returns:
            List of message dictionaries with timestamp, author, content
        """
        if not self.tab:
            logger.error("Not connected to Slack")
            return []

        assert self.tab is not None

        try:
            # Type annotation for extracted messages
            result = self.tab.Runtime.evaluate(
                expression="""
                (() => {
                    const messages = [];

                    // Find the message pane
                    const messagePane = document.querySelector('.p-message_pane') ||
                                       document.querySelector('.c-message_list');

                    if (!messagePane) {
                        return { error: 'Message pane not found' };
                    }

                    // Find all elements with timestamps (indicates messages)
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
                                    };

                                    // Try to find author (usually before timestamp)
                                    const lines = parentText.split('\\n');
                                    if (lines.length > 1) {
                                        message.author = lines[0];
                                        message.content = lines.slice(2).join('\\n');
                                    }

                                    // Create unique ID (author + timestamp + first 50 chars)
                                    message.id = (message.author || 'unknown') + '-' +
                                                (message.timestamp || 'no-time') + '-' +
                                                parentText.substring(0, 50).replace(/[^a-zA-Z0-9]/g, '');

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
                        messages: unique
                    };
                })()
                """,
                returnByValue=True,
            )

            data = result.get("result", {}).get("value", {})

            if data.get("error"):
                logger.warning(f"Extraction error: {data['error']}")
                return []

            messages: list[dict[str, Any]] = data.get("messages", [])
            logger.info(f"Extracted {len(messages)} messages from current view")

            return messages

        except Exception as e:
            logger.error(f"Error extracting messages: {e}")
            return []

    def filter_new_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Filter out messages we've already seen

        Args:
            messages: List of extracted messages

        Returns:
            List of new messages only
        """
        new_messages = []

        for msg in messages:
            msg_id = msg.get("id", "")

            if msg_id and msg_id not in self.seen_message_ids:
                new_messages.append(msg)
                self.seen_message_ids.add(msg_id)

        logger.info(
            f"Found {len(new_messages)} new messages (filtered {len(messages) - len(new_messages)})"
        )

        return new_messages

    def detect_task_creating_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Detect which messages likely contain tasks

        Args:
            messages: List of messages

        Returns:
            List of messages that likely contain tasks
        """
        if not self.llm_parser or not messages:
            return []

        task_messages = []

        for msg in messages:
            content = msg.get("content", "")

            # Quick heuristic filter first (save LLM calls)
            task_indicators = [
                "can you",
                "could you",
                "please",
                "need to",
                "todo",
                "action item",
                "@",  # Mentions often indicate assignments
                "?",  # Questions often become tasks
                "should",
                "must",
                "blocked",
                "help",
            ]

            if any(indicator in content.lower() for indicator in task_indicators):
                msg["likely_task"] = True
                task_messages.append(msg)
            else:
                msg["likely_task"] = False

        logger.info(
            f"Filtered to {len(task_messages)} potential task-creating messages (from {len(messages)})"
        )

        return task_messages

    def extract_tasks_from_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Extract structured tasks from messages using LLM

        Args:
            messages: List of messages

        Returns:
            List of extracted tasks
        """
        if not self.llm_parser or not messages:
            return []

        # Combine messages into a single context for LLM
        combined_messages = "\n\n".join(
            [
                f"**{msg.get('author', 'Unknown')}** ({msg.get('timestamp', 'unknown time')}):\n{msg.get('content', '')}"
                for msg in messages
            ]
        )

        # Build extraction prompt
        prompt = f"""You are analyzing Slack messages to extract action items and tasks.

# Slack Messages
{combined_messages}

---

# Task
Extract any action items, tasks, or work that needs to be done from these messages.

For each task, extract:
- **task**: Clear description of what needs to be done
- **assignee**: Who should do it (person mentioned, or "unassigned")
- **context**: Why it matters, any constraints or dependencies
- **priority**: high, medium, or low
- **source_author**: Who created/mentioned this task
- **channel**: If mentioned (otherwise "unknown")

**Guidelines**:
- Only extract if there's actual work to be done
- Questions that need answers are tasks
- Requests for help are tasks
- "Can you..." / "Could you..." / "Please..." are tasks
- Ignore casual conversation, greetings, status updates
- If someone volunteers ("I'll do X"), that's a task for them

Return a JSON array of tasks. If no tasks found, return empty array: []

Each task should match this structure:
{{
  "task": "string",
  "assignee": "string",
  "context": "string",
  "priority": "high" | "medium" | "low",
  "source_author": "string",
  "channel": "string"
}}"""

        try:
            logger.info("Extracting tasks from messages using LLM...")

            response = self.llm_parser.client.chat.completions.create(
                model=self.llm_parser.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            )

            response_text = response.choices[0].message.content

            # Try to extract JSON from response
            # Sometimes LLM wraps in markdown code blocks
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]

            extracted_tasks: list[dict[str, Any]] = json.loads(response_text.strip())

            logger.info(f"Extracted {len(extracted_tasks)} tasks from {len(messages)} messages")

            return extracted_tasks

        except Exception as e:
            logger.error(f"Error extracting tasks with LLM: {e}")
            return []

    def write_tasks_to_obsidian(self, tasks: list[dict[str, Any]]):
        """
        Write extracted tasks to Obsidian daily note

        Args:
            tasks: List of extracted tasks
        """
        if not tasks:
            logger.info("No tasks to write")
            return

        # Get today's daily note path
        today = datetime.now()
        daily_note_path = (
            self.vault_path
            / "00_Inbox"
            / "Slack"
            / f"{today.strftime('%Y-%m-%d')} - Slack Captures.md"
        )

        # Ensure directory exists
        daily_note_path.parent.mkdir(parents=True, exist_ok=True)

        # Read existing content or create new
        if daily_note_path.exists():
            with open(daily_note_path, encoding="utf-8") as f:
                existing_content = f.read()
        else:
            # Create new daily note
            existing_content = f"""---
date: {today.strftime("%Y-%m-%d")}
type: slack-capture
tags: [slack, tasks, automated]
---

# Slack Task Captures - {today.strftime("%Y-%m-%d")}

"""

        # Append new tasks
        task_section = f"\n## Captured at {datetime.now().strftime('%H:%M:%S')}\n\n"

        for task in tasks:
            assignee = task.get("assignee", "unassigned")
            task_text = task["task"]
            context = task.get("context", "")
            priority = task.get("priority", "medium")
            source_author = task.get("source_author", "unknown")
            channel = task.get("channel", "unknown")

            # Format task with Obsidian Tasks plugin emoji format
            priority_emoji = {"high": "⏫", "medium": "🔽", "low": "⏬"}.get(priority, "")

            task_section += f"### @{assignee}\n\n"
            task_section += f"- [ ] {task_text} {priority_emoji}\n"

            if context:
                task_section += f"  - **Context**: {context}\n"
            if source_author:
                task_section += f"  - **From**: {source_author}\n"
            if channel and channel != "unknown":
                task_section += f"  - **Channel**: #{channel}\n"

            task_section += "\n"

        # Write combined content
        final_content = existing_content + task_section

        with open(daily_note_path, "w", encoding="utf-8") as f:
            f.write(final_content)

        logger.info(f"✅ Wrote {len(tasks)} tasks to {daily_note_path}")

    def monitor_loop(self, max_iterations: int | None = None):
        """
        Main monitoring loop

        Args:
            max_iterations: Maximum iterations to run (None = infinite)
        """
        if not self.connect():
            logger.error("Failed to connect to Slack. Exiting.")
            return

        iteration = 0

        try:
            logger.info("Starting monitoring loop...")

            while True:
                iteration += 1

                if max_iterations and iteration > max_iterations:
                    logger.info(f"Reached max iterations ({max_iterations}). Stopping.")
                    break

                try:
                    logger.info(f"\n--- Iteration {iteration} ---")

                    # Extract messages from current view
                    all_messages = self.extract_messages()

                    # Filter to new messages only
                    new_messages = self.filter_new_messages(all_messages)

                    if new_messages:
                        # Detect which messages might have tasks
                        potential_task_messages = self.detect_task_creating_messages(new_messages)

                        if potential_task_messages:
                            # Extract structured tasks using LLM
                            tasks = self.extract_tasks_from_messages(potential_task_messages)

                            if tasks:
                                # Write to Obsidian
                                self.write_tasks_to_obsidian(tasks)
                            else:
                                logger.info("No tasks extracted from messages")
                        else:
                            logger.info("No potential task-creating messages found")
                    else:
                        logger.info("No new messages since last check")

                    # Update last check time
                    self.last_check_time = datetime.now()

                    # Sleep until next check
                    logger.info(f"Sleeping for {self.check_interval}s...")
                    time.sleep(self.check_interval)

                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    logger.error(f"Error in monitoring iteration: {e}")
                    logger.exception("Detailed error:")
                    # Continue to next iteration
                    time.sleep(self.check_interval)

        except KeyboardInterrupt:
            logger.info("\nMonitoring stopped by user")
        finally:
            self.disconnect()


def main():
    """Main entry point for CLI"""
    import argparse

    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("logs/slack_monitor.log"),
            logging.StreamHandler(),
        ],
    )

    # Parse arguments
    parser = argparse.ArgumentParser(description="Monitor Slack messages via CDP")
    parser.add_argument("--vault", type=str, required=True, help="Path to Obsidian vault")
    parser.add_argument("--port", type=int, default=9222, help="CDP port (default: 9222)")
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Check interval in seconds (default: 60)",
    )
    parser.add_argument("--no-llm", action="store_true", help="Disable LLM task extraction")
    parser.add_argument(
        "--max-iterations",
        type=int,
        help="Maximum iterations to run (for testing)",
    )

    args = parser.parse_args()

    # Initialize monitor
    monitor = SlackCDPMonitor(
        vault_path=args.vault,
        enable_llm=not args.no_llm,
        cdp_port=args.port,
        check_interval=args.interval,
    )

    # Run monitoring loop
    monitor.monitor_loop(max_iterations=args.max_iterations)


if __name__ == "__main__":
    main()
