#!/usr/bin/env -S uv run --quiet python
"""
Granola Sync - Main entry point for automated meeting sync

Fetches new meetings from Granola API and writes them to Obsidian vault.
Designed to be run via cron every 15 minutes.
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add src to path (go up one level from scripts/)
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from processor import GranolaProcessor


def setup_logging():
    """Configure logging with file and console handlers"""
    # Go up to project root, then into logs/
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)

    log_file = log_dir / "granola_sync.log"

    # Create logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Remove existing handlers
    logger.handlers.clear()

    # File handler (detailed logs)
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(file_formatter)

    # Console handler (concise logs)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    console_handler.setFormatter(console_formatter)

    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


def write_sync_status(results):
    """Write sync status to file for monitoring"""
    # Go up to project root, then into logs/
    status_file = Path(__file__).parent.parent / "logs" / "status.json"

    status = {
        "last_run": results["timestamp"],
        "fetched": results["fetched"],
        "processed": results["processed"],
        "failed": results["failed"],
        "status": "success" if results["failed"] == 0 else "partial_failure",
        "errors": results.get("errors", []),
    }

    with open(status_file, "w") as f:
        json.dump(status, f, indent=2)


def main():
    """Main sync function"""
    logger = setup_logging()

    logger.info("=" * 60)
    logger.info("Granola Sync Started")
    logger.info("=" * 60)

    try:
        # Initialize processor
        processor = GranolaProcessor()

        # Process new meetings
        results = processor.process_new_meetings()

        # Write status file
        write_sync_status(results)

        # Log results
        logger.info(
            f"Sync complete: {results['processed']} notes created, {results['failed']} failed"
        )

        if results["notes_created"]:
            logger.info("Created notes:")
            for note_path in results["notes_created"]:
                logger.info(f"  ✓ {Path(note_path).name}")

        if results["errors"]:
            logger.error("Errors occurred during sync:")
            for error in results["errors"]:
                logger.error(f"  ✗ {error}")

        # Exit code
        if results["failed"] > 0:
            sys.exit(1)  # Partial failure
        else:
            sys.exit(0)  # Success

    except Exception as e:
        logger.error(f"Fatal error during sync: {e}")
        logger.exception("Detailed error:")

        # Write error status
        write_sync_status(
            {
                "timestamp": datetime.now().isoformat(),
                "fetched": 0,
                "processed": 0,
                "failed": 1,
                "errors": [str(e)],
            }
        )

        sys.exit(2)  # Fatal error


if __name__ == "__main__":
    main()
