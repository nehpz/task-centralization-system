"""
End-to-End Processor

Main orchestrator that fetches Granola documents and writes them to Obsidian.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from credential_manager import CredentialManager
from granola_fetcher import GranolaFetcher
from obsidian_writer import ObsidianWriter
from sync_state import SyncStateManager

logger = logging.getLogger(__name__)


class GranolaProcessor:
    """Main processor for Granola → Obsidian pipeline"""

    def __init__(self, enable_llm: bool = True):
        """
        Initialize processor

        Args:
            enable_llm: Enable LLM-based action item extraction (default: True)
        """
        self.cred_manager = CredentialManager()
        self.fetcher = GranolaFetcher(self.cred_manager)
        self.writer = ObsidianWriter(self.cred_manager)
        self.state = SyncStateManager()

        # Initialize LLM parser if enabled
        self.llm_parser = None
        if enable_llm:
            try:
                from llm_parser_perplexity import LLMParser

                # Get LLM config from credentials
                llm_config = self.cred_manager.get_llm_config()
                if llm_config:
                    api_key = llm_config.get("api_key")
                    model = llm_config.get("model", "sonar-pro")
                    self.llm_parser = LLMParser(api_key=api_key, model=model)
                    logger.info(
                        f"GranolaProcessor initialized with LLM enrichment (model: {model})"
                    )
                else:
                    # Fallback to environment variable
                    self.llm_parser = LLMParser()
                    logger.info("GranolaProcessor initialized with LLM enrichment (using env vars)")
            except Exception as e:
                logger.warning(
                    f"LLM parser initialization failed: {e}. Continuing without LLM enrichment."
                )
        else:
            logger.info("GranolaProcessor initialized (LLM enrichment disabled)")

    def process_new_meetings(self) -> dict[str, Any]:
        """
        Fetch new meetings and process them

        Returns:
            Dictionary with processing results
        """
        logger.info("Starting processing run...")

        results: dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "fetched": 0,
            "processed": 0,
            "failed": 0,
            "skipped": 0,
            "notes_created": [],
            "errors": [],
        }

        try:
            # Fetch new documents
            logger.info("Fetching new documents from Granola API...")
            documents = self.fetcher.fetch_new_documents()

            if documents is None:
                logger.error("Failed to fetch documents from Granola API")
                results["errors"].append("API fetch failed")
                return results

            results["fetched"] = len(documents)
            logger.info(f"Fetched {len(documents)} new documents")

            if len(documents) == 0:
                logger.info("No new documents to process")
                return results

            # Process each document
            for i, doc in enumerate(documents, 1):
                doc_id = doc.get("id", "unknown")
                title = doc.get("title", "Untitled")

                logger.info(f"Processing document {i}/{len(documents)}: {title}")

                try:
                    # Check if already processed
                    if self.state.is_processed(doc_id):
                        logger.info("  → Already processed, skipping")
                        results["skipped"] += 1
                        continue

                    # Check if document is valid meeting
                    if not doc.get("valid_meeting", True):
                        logger.info(f"  Skipping invalid meeting: {doc_id}")
                        results["skipped"] += 1
                        continue

                    # Write to Obsidian
                    filepath = self.writer.write_meeting_note(doc)

                    if filepath:
                        results["processed"] += 1
                        results["notes_created"].append(str(filepath))
                        logger.info(f"  ✓ Created: {filepath.name}")

                        # Mark as processed
                        self.state.mark_processed(doc_id)

                        # Enrich with LLM if enabled
                        if self.llm_parser:
                            try:
                                self._enrich_note_with_llm(filepath)
                                logger.info("  ✓ Enriched with LLM parsing")
                            except Exception as e:
                                logger.warning(f"  ⚠ LLM enrichment failed: {e}")
                                # Don't fail the whole process if LLM enrichment fails
                    else:
                        results["failed"] += 1
                        results["errors"].append(f"Failed to write note for {doc_id}")
                        logger.error(f"  ✗ Failed to create note for {doc_id}")

                except Exception as e:
                    results["failed"] += 1
                    error_msg = f"Error processing {doc_id}: {str(e)}"
                    results["errors"].append(error_msg)
                    logger.error(f"  ✗ {error_msg}")
                    logger.exception("Detailed error:")

            logger.info(
                f"Processing complete: {results['processed']} notes created, {results['failed']} failed"
            )

        except Exception as e:
            logger.error(f"Fatal error during processing: {e}")
            logger.exception("Detailed error:")
            results["errors"].append(f"Fatal error: {str(e)}")

        return results

    def process_specific_document(self, doc_id: str) -> bool:
        """
        Process a specific Granola document by ID

        Args:
            doc_id: Granola document ID

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Processing specific document: {doc_id}")

        try:
            # Fetch the document
            doc = self.fetcher.get_document_by_id(doc_id)

            if not doc:
                logger.error(f"Document not found: {doc_id}")
                return False

            # Write to Obsidian
            filepath = self.writer.write_meeting_note(doc)

            if filepath:
                logger.info(f"✓ Created: {filepath}")
                return True
            logger.error(f"Failed to create note for {doc_id}")
            return False

        except Exception as e:
            logger.error(f"Error processing document {doc_id}: {e}")
            logger.exception("Detailed error:")
            return False

    def process_backfill(self, days: int = 7) -> dict[str, Any]:
        """
        Process all documents from the last N days

        Args:
            days: Number of days to backfill

        Returns:
            Dictionary with processing results
        """
        logger.info(f"Starting backfill for last {days} days...")

        results: dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "days": days,
            "fetched": 0,
            "processed": 0,
            "failed": 0,
            "skipped": 0,
            "notes_created": [],
            "errors": [],
        }

        try:
            # Fetch all documents (no date filter)
            logger.info("Fetching recent documents...")
            documents = self.fetcher.fetch_documents(limit=100)

            if documents is None:
                logger.error("Failed to fetch documents")
                results["errors"].append("API fetch failed")
                return results

            results["fetched"] = len(documents)
            logger.info(f"Fetched {len(documents)} documents")

            # Process each document
            for i, doc in enumerate(documents, 1):
                doc_id = doc.get("id", "unknown")
                title = doc.get("title", "Untitled")

                logger.info(f"Processing {i}/{len(documents)}: {title}")

                try:
                    # Check if already processed
                    if self.state.is_processed(doc_id):
                        logger.info("  → Already processed, skipping")
                        results["skipped"] += 1
                        continue

                    # Write to Obsidian
                    filepath = self.writer.write_meeting_note(doc)

                    if filepath:
                        results["processed"] += 1
                        results["notes_created"].append(str(filepath))
                        logger.info(f"  ✓ Created: {filepath.name}")

                        # Mark as processed
                        self.state.mark_processed(doc_id)
                    else:
                        results["failed"] += 1
                        logger.error("  ✗ Failed to create note")

                except Exception as e:
                    results["failed"] += 1
                    error_msg = f"Error processing {doc_id}: {str(e)}"
                    results["errors"].append(error_msg)
                    logger.error(f"  ✗ {error_msg}")

            logger.info(f"Backfill complete: {results['processed']} notes created")

        except Exception as e:
            logger.error(f"Fatal error during backfill: {e}")
            logger.exception("Detailed error:")
            results["errors"].append(f"Fatal error: {str(e)}")

        return results

    def _enrich_note_with_llm(self, filepath: Path) -> None:
        """
        Enrich a meeting note with LLM-extracted action items and decisions

        Args:
            filepath: Path to the meeting note to enrich
        """
        import re

        import yaml

        # Read the file
        with open(filepath, encoding="utf-8") as f:
            content = f.read()

        # Extract frontmatter and content
        frontmatter_match = re.match(r"^---\n(.*?)\n---\n(.*)$", content, re.DOTALL)

        if not frontmatter_match:
            logger.warning(f"No frontmatter found in {filepath}, skipping LLM enrichment")
            return

        frontmatter_yaml = frontmatter_match.group(1)
        markdown_content = frontmatter_match.group(2)

        # Parse frontmatter
        metadata = yaml.safe_load(frontmatter_yaml)

        # Check if LLM parser is available
        if not self.llm_parser:
            logger.warning("LLM parser not available, skipping enrichment")
            return

        # Parse with LLM
        parsed_data = self.llm_parser.parse_meeting(markdown_content, metadata)

        # Generate enriched content
        enriched_content = self.llm_parser.enrich_meeting_note(
            markdown_content, metadata, parsed_data
        )

        # Update metadata to indicate LLM enrichment
        metadata["llm_enriched"] = True
        metadata["llm_model"] = f"perplexity-{self.llm_parser.model}"

        # Write enriched note back
        enriched_frontmatter = yaml.dump(metadata, default_flow_style=False, sort_keys=False)
        full_content = f"---\n{enriched_frontmatter}---\n\n{enriched_content}"

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(full_content)


def main():
    """Main entry point for CLI"""
    import argparse
    import json

    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.FileHandler("logs/processor.log"), logging.StreamHandler()],
    )

    # Parse arguments
    parser = argparse.ArgumentParser(description="Process Granola meetings to Obsidian")
    parser.add_argument(
        "--backfill", type=int, metavar="DAYS", help="Backfill last N days of meetings"
    )
    parser.add_argument("--doc-id", type=str, metavar="ID", help="Process specific document by ID")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")

    args = parser.parse_args()

    # Initialize processor
    processor = GranolaProcessor()

    # Execute requested action
    if args.doc_id:
        # Process specific document
        success = processor.process_specific_document(args.doc_id)
        if args.json:
            print(json.dumps({"success": success}))
        elif success:
            print("✓ Document processed successfully")
        else:
            print("✗ Failed to process document")

    elif args.backfill:
        # Backfill mode
        results = processor.process_backfill(days=args.backfill)
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            print("\n=== Backfill Results ===")
            print(f"Fetched: {results['fetched']}")
            print(f"Processed: {results['processed']}")
            print(f"Skipped: {results['skipped']}")
            print(f"Failed: {results['failed']}")
            if results["errors"]:
                print("\nErrors:")
                for error in results["errors"]:
                    print(f"  - {error}")

    else:
        # Default: process new meetings
        results = processor.process_new_meetings()
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            print("\n=== Processing Results ===")
            print(f"Fetched: {results['fetched']}")
            print(f"Processed: {results['processed']}")
            print(f"Failed: {results['failed']}")
            if results["notes_created"]:
                print("\nCreated notes:")
                for note in results["notes_created"]:
                    print(f"  ✓ {Path(note).name}")
            if results["errors"]:
                print("\nErrors:")
                for error in results["errors"]:
                    print(f"  - {error}")


if __name__ == "__main__":
    main()
