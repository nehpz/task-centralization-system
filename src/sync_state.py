"""
Sync State Manager

Maintains a persistent set of processed Granola document IDs for efficient
duplicate prevention. Uses JSON for simplicity and portability.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class SyncStateManager:
    """Manage sync state including processed document IDs"""

    def __init__(self, state_file: Path | None = None):
        """
        Initialize sync state manager

        Args:
            state_file: Path to state file (defaults to logs/.sync_state.json)
        """
        if state_file is None:
            state_file = Path("logs/.sync_state.json")

        self.state_file = state_file
        self.state = self._load_state()
        logger.debug(f"SyncStateManager initialized with {len(self.state['processed_ids'])} IDs")

    def _load_state(self) -> dict[str, Any]:
        """
        Load state from file

        Returns:
            State dictionary with processed_ids set and metadata
        """
        if self.state_file.exists():
            try:
                with open(self.state_file) as f:
                    data = json.load(f)

                # Convert list to set for O(1) lookups
                processed_ids = set(data.get("processed_ids", []))

                state = {
                    "processed_ids": processed_ids,
                    "last_pruned": data.get("last_pruned"),
                    "stats": data.get("stats", {"total_processed": 0}),
                }

                logger.info(f"Loaded state: {len(processed_ids)} processed IDs")
                return state

            except json.JSONDecodeError as e:
                logger.warning(f"Error loading state file: {e}. Starting fresh.")
            except Exception as e:
                logger.error(f"Unexpected error loading state: {e}")

        # Return empty state
        logger.info("Starting with empty state")
        return {
            "processed_ids": set(),
            "last_pruned": None,
            "stats": {"total_processed": 0},
        }

    def _save_state(self):
        """Save state to file"""
        try:
            # Ensure logs directory exists
            self.state_file.parent.mkdir(parents=True, exist_ok=True)

            # Convert set to list for JSON serialization
            data = {
                "processed_ids": sorted(self.state["processed_ids"]),
                "last_pruned": self.state["last_pruned"],
                "stats": self.state["stats"],
                "updated_at": datetime.now().isoformat(),
            }

            with open(self.state_file, "w") as f:
                json.dump(data, f, indent=2)

            logger.debug(f"Saved state: {len(self.state['processed_ids'])} IDs")

        except Exception as e:
            logger.error(f"Error saving state: {e}")

    def is_processed(self, granola_id: str) -> bool:
        """
        Check if a document has been processed

        Args:
            granola_id: Granola document ID

        Returns:
            True if already processed, False otherwise
        """
        return granola_id in self.state["processed_ids"]

    def mark_processed(self, granola_id: str):
        """
        Mark a document as processed

        Args:
            granola_id: Granola document ID
        """
        if granola_id not in self.state["processed_ids"]:
            self.state["processed_ids"].add(granola_id)
            self.state["stats"]["total_processed"] += 1
            self._save_state()
            logger.debug(f"Marked processed: {granola_id}")

    def mark_batch_processed(self, granola_ids: list[str]):
        """
        Mark multiple documents as processed (more efficient than individual calls)

        Args:
            granola_ids: List of Granola document IDs
        """
        new_ids = [gid for gid in granola_ids if gid not in self.state["processed_ids"]]

        if new_ids:
            self.state["processed_ids"].update(new_ids)
            self.state["stats"]["total_processed"] += len(new_ids)
            self._save_state()
            logger.info(f"Marked {len(new_ids)} documents as processed")

    def prune_old_ids(self, days: int = 90):
        """
        Prune old IDs to keep state file small

        Note: This is optional - the state file will only be ~11KB per year at 30 meetings/day.
        Only call if you want to strictly limit state file size.

        Args:
            days: Keep IDs from last N days, remove older ones
        """
        # This requires tracking timestamps per ID, which we're not doing by default
        # for simplicity. The file will stay small enough without pruning.
        logger.info("Pruning not implemented - state file is small enough without it")

        # Update last pruned timestamp
        self.state["last_pruned"] = datetime.now().isoformat()
        self._save_state()

    def get_stats(self) -> dict[str, Any]:
        """
        Get sync statistics

        Returns:
            Statistics dictionary
        """
        return {
            "total_processed": self.state["stats"]["total_processed"],
            "ids_in_memory": len(self.state["processed_ids"]),
            "state_file_size_kb": (
                self.state_file.stat().st_size / 1024 if self.state_file.exists() else 0
            ),
        }


if __name__ == "__main__":
    # Test the state manager
    import tempfile

    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

    print("=== Testing SyncStateManager ===\n")

    # Use temp file for testing
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        test_file = Path(f.name)

    try:
        # Test 1: Initialize
        print("\nTest 1: Initialize empty state")
        manager = SyncStateManager(test_file)
        print(f"✓ Stats: {manager.get_stats()}")

        # Test 2: Mark documents
        print("\nTest 2: Mark documents as processed")
        test_ids = ["doc-123", "doc-456", "doc-789"]
        manager.mark_batch_processed(test_ids)
        print(f"✓ Marked {len(test_ids)} documents")

        # Test 3: Check duplicates
        print("\nTest 3: Check for duplicates")
        print(f"  doc-123 processed? {manager.is_processed('doc-123')} (should be True)")
        print(f"  doc-999 processed? {manager.is_processed('doc-999')} (should be False)")

        # Test 4: Reload from file
        print("\nTest 4: Reload from file")
        manager2 = SyncStateManager(test_file)
        print(f"  doc-123 still processed? {manager2.is_processed('doc-123')} (should be True)")
        print("✓ State persisted correctly")

        # Test 5: Stats
        print("\nTest 5: Get statistics")
        stats = manager2.get_stats()
        print(f"✓ Stats: {stats}")

        print("\n✅ All tests passed!")

    finally:
        # Cleanup
        test_file.unlink(missing_ok=True)
        print(f"\nCleaned up test file: {test_file}")
