"""
Granola Document Fetcher

Poll Granola API for new meeting documents.

Based on Joseph Thacker's reverse engineering:
https://josephthacker.com/hacking/2025/05/08/reverse-engineering-granola-notes.html
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import requests

from credential_manager import CredentialManager

logger = logging.getLogger(__name__)


class GranolaFetcher:
    """Fetch documents from Granola API"""

    API_BASE_URL = "https://api.granola.ai/v2"
    API_VERSION = "5.354.0"

    def __init__(self, credential_manager: CredentialManager):
        """
        Initialize Granola fetcher

        Args:
            credential_manager: CredentialManager instance
        """
        self.cred_manager = credential_manager
        self.token = self.cred_manager.get_granola_token()

        if not self.token:
            raise ValueError("Granola access token not available")

        self.last_check_file = Path("logs/.last_sync")
        logger.info("GranolaFetcher initialized")

    def fetch_documents(
        self, limit: int = 100, offset: int = 0, created_after: datetime | None = None
    ) -> list[dict[str, Any]] | None:
        """
        Fetch documents from Granola API

        Args:
            limit: Maximum number of documents to fetch
            offset: Offset for pagination
            created_after: Only fetch documents created after this timestamp

        Returns:
            List of document dictionaries, or None if request failed
        """
        url = f"{self.API_BASE_URL}/get-documents"

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "*/*",
            "User-Agent": f"Granola/{self.API_VERSION}",
            "X-Client-Version": self.API_VERSION,
        }

        payload = {"limit": limit, "offset": offset, "include_last_viewed_panel": True}

        # Add created_after filter if provided
        if created_after:
            payload["created_after"] = created_after.isoformat()
            logger.debug(f"Fetching documents created after {created_after.isoformat()}")

        try:
            logger.info(f"Fetching documents from Granola API (limit={limit}, offset={offset})")
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()

            data = response.json()

            # Extract documents array
            if "docs" in data:
                documents = data["docs"]
                logger.info(f"Successfully fetched {len(documents)} documents")
                return documents
            logger.warning("No 'docs' key in API response")
            logger.debug(f"Response keys: {data.keys()}")
            return []

        except requests.exceptions.Timeout:
            logger.error("Request timed out after 30 seconds")
            return None
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error: {e}")
            logger.debug(f"Response: {response.text if response else 'No response'}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return None

    def fetch_new_documents(self) -> list[dict[str, Any]] | None:
        """
        Fetch documents created since last check

        Returns:
            List of new documents, or None if request failed
        """
        last_check = self._load_last_check()
        logger.info(f"Fetching documents since {last_check.isoformat()}")

        documents = self.fetch_documents(created_after=last_check)

        if documents is not None:
            self._update_last_check()
            logger.info(f"Found {len(documents)} new documents")
            return documents

        return None

    def _load_last_check(self) -> datetime:
        """
        Load timestamp of last successful check

        Returns:
            Datetime of last check, or 7 days ago if first run
        """
        if self.last_check_file.exists():
            try:
                with open(self.last_check_file) as f:
                    timestamp_str = f.read().strip()
                    last_check = datetime.fromisoformat(timestamp_str)
                    logger.debug(f"Loaded last check: {last_check.isoformat()}")
                    return last_check
            except Exception as e:
                logger.warning(f"Error loading last check timestamp: {e}")

        # First run: fetch last 7 days
        first_run = datetime.now() - timedelta(days=7)
        logger.info(f"First run: fetching documents from last 7 days ({first_run.isoformat()})")
        return first_run

    def _update_last_check(self):
        """
        Save current timestamp as last successful check
        """
        try:
            now = datetime.now()
            with open(self.last_check_file, "w") as f:
                f.write(now.isoformat())
            logger.debug(f"Updated last check to {now.isoformat()}")
        except Exception as e:
            logger.error(f"Error saving last check timestamp: {e}")

    def get_document_by_id(self, doc_id: str) -> dict[str, Any] | None:
        """
        Get a specific document by ID

        Args:
            doc_id: Granola document ID

        Returns:
            Document dictionary, or None if not found
        """
        # Fetch recent documents and search for the ID
        documents = self.fetch_documents(limit=100)

        if not documents:
            return None

        for doc in documents:
            if doc.get("id") == doc_id:
                logger.info(f"Found document: {doc_id}")
                return doc

        logger.warning(f"Document not found: {doc_id}")
        return None


if __name__ == "__main__":
    # Test Granola API access
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

    print("=== Testing Granola API Access ===\n")

    try:
        # Initialize
        cred_manager = CredentialManager()
        fetcher = GranolaFetcher(cred_manager)

        # Test 1: Fetch recent documents
        print("\nTest 1: Fetching recent documents...")
        documents = fetcher.fetch_documents(limit=5)

        if documents:
            print(f"\n✅ Success! Found {len(documents)} documents")
            print("\nFirst document:")
            if documents:
                doc = documents[0]
                print(f"  ID: {doc.get('id')}")
                print(f"  Title: {doc.get('title', 'Untitled')}")
                print(f"  Created: {doc.get('created_at')}")
                print(f"  Has content: {'last_viewed_panel' in doc}")
        else:
            print("\n❌ Failed to fetch documents")

        # Test 2: Fetch new documents (incremental)
        print("\n\nTest 2: Testing incremental fetch...")
        new_docs = fetcher.fetch_new_documents()

        if new_docs is not None:
            print(f"\n✅ Incremental fetch working! Found {len(new_docs)} new documents")
        else:
            print("\n❌ Incremental fetch failed")

    except ValueError as e:
        print(f"\n❌ Error: {e}")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        logger.exception("Detailed error:")
