"""
Obsidian Writer

Write meeting notes to Obsidian vault with YAML frontmatter and markdown content.
"""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from credential_manager import CredentialManager
from format_converter import MetadataExtractor, ProseMirrorConverter

logger = logging.getLogger(__name__)


class ObsidianWriter:
    """Write meeting notes to Obsidian vault"""

    def __init__(self, credential_manager: CredentialManager):
        """
        Initialize Obsidian writer

        Args:
            credential_manager: CredentialManager instance
        """
        self.cred_manager = credential_manager
        self.vault_path = self.cred_manager.get_vault_path()
        self.inbox_path = self.vault_path / "00_Inbox" / "Meetings"
        self.user_info = self.cred_manager.get_user_info()

        # Create inbox directory if it doesn't exist
        self.inbox_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"ObsidianWriter initialized (vault: {self.vault_path})")

    def write_meeting_note(self, doc: dict[str, Any]) -> Path | None:
        """
        Write a meeting note to the vault

        Args:
            doc: Granola document dictionary

        Returns:
            Path to created note, or None if failed
        """
        try:
            # Extract metadata
            metadata = MetadataExtractor.extract_metadata(doc)

            # Convert content to markdown
            converter = ProseMirrorConverter()
            if "content" in metadata and metadata["content"]:
                markdown_content = converter.convert(metadata["content"])
            else:
                logger.warning(f"No content found for document {metadata['granola_id']}")
                markdown_content = "_No content available_"

            # Generate filename
            filename = self._generate_filename(metadata)

            # Generate full note with frontmatter
            note_content = self._generate_note(metadata, markdown_content)

            # Write to file
            filepath: Path = self.inbox_path / filename

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(note_content)

            logger.info(f"Created meeting note: {filename}")
            return filepath

        except Exception as e:
            logger.error(f"Error writing meeting note: {e}")
            logger.exception("Detailed error:")
            return None

    def _generate_filename(self, metadata: dict[str, Any]) -> str:
        """
        Generate filename for meeting note

        Format: YYYY-MM-DD - [Meeting Title].md

        Args:
            metadata: Meeting metadata

        Returns:
            Filename string
        """
        # Parse created_at timestamp
        created_at = metadata.get("created_at")
        if created_at:
            try:
                dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                date_str = dt.strftime("%Y-%m-%d")
            except (ValueError, AttributeError):
                date_str = datetime.now().strftime("%Y-%m-%d")
        else:
            date_str = datetime.now().strftime("%Y-%m-%d")

        # Sanitize title for filename
        title = metadata.get("title", "Untitled Meeting")
        safe_title = self._sanitize_filename(title)

        return f"{date_str} - {safe_title}.md"

    def _sanitize_filename(self, filename: str) -> str:
        """
        Sanitize string for use in filename

        Args:
            filename: Original filename

        Returns:
            Safe filename
        """
        # Remove or replace invalid characters
        safe = re.sub(r'[<>:"/\\|?*!]', "", filename)

        # Replace multiple spaces with single space
        safe = re.sub(r"\s+", " ", safe)

        # Trim and limit length
        safe = safe.strip()[:100]

        return safe

    def _generate_note(self, metadata: dict[str, Any], markdown_content: str) -> str:
        """
        Generate complete note with frontmatter and content

        Args:
            metadata: Meeting metadata
            markdown_content: Converted markdown content

        Returns:
            Complete note content
        """
        # Build frontmatter
        frontmatter = self._build_frontmatter(metadata)

        # Build note sections
        title = metadata.get("title", "Untitled Meeting")
        header = self._build_header(metadata)

        # Combine into full note
        note = f"""---
{frontmatter}---

# {title}

{header}

## Notes

{markdown_content}

---

**Generated**: {datetime.now().isoformat()} via Task Centralization System
**Source**: Granola API (automatic capture)
**Granola ID**: `{metadata.get("granola_id")}`
"""

        return note

    def _build_frontmatter(self, metadata: dict[str, Any]) -> str:
        """
        Build YAML frontmatter

        Args:
            metadata: Meeting metadata

        Returns:
            YAML frontmatter string
        """
        # Parse date/time
        created_at = metadata.get("created_at")
        if created_at:
            try:
                dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                date = dt.strftime("%Y-%m-%d")
                time = dt.strftime("%H:%M")
            except (ValueError, AttributeError):
                date = datetime.now().strftime("%Y-%m-%d")
                time = datetime.now().strftime("%H:%M")
        else:
            date = datetime.now().strftime("%Y-%m-%d")
            time = datetime.now().strftime("%H:%M")

        # Build frontmatter dict
        fm = {
            "date": date,
            "time": time,
            "meeting": metadata.get("title", "Untitled Meeting"),
            "source": "granola-api",
            "granola_id": metadata.get("granola_id"),
            "type": "meeting-note",
            "status": "auto-generated",
        }

        # Add attendees as wikilinks
        attendees = metadata.get("attendees", [])
        if attendees:
            fm["attendees"] = [f"[[{self._extract_name(email)}]]" for email in attendees]

        # Add optional fields if available
        if metadata.get("duration_minutes"):
            fm["duration"] = f"{metadata['duration_minutes']} min"

        if metadata.get("summary"):
            fm["summary"] = metadata["summary"]

        if metadata.get("calendar_event_id"):
            fm["calendar_event_id"] = metadata["calendar_event_id"]

        # Convert to YAML
        yaml_str = yaml.dump(fm, default_flow_style=False, allow_unicode=True, sort_keys=False)

        return yaml_str

    def _extract_name(self, email_or_name: str) -> str:
        """
        Extract person name from email or name string.
        Handles "Full Name <email@example.com>" format.

        Args:
            email_or_name: Email address or name string.

        Returns:
            Person name suitable for a note title.
        """
        # Check for "Name <email>" format
        match = re.match(r"(.+?)\s*<.*>", email_or_name)
        if match:
            return match.group(1).strip()

        # If it's just an email, extract the name part
        if "@" in email_or_name:
            name_part = email_or_name.split("@")[0]

            # Convert common patterns to readable names
            # e.g., "john.doe" -> "John Doe"
            name_part = name_part.replace(".", " ").replace("_", " ")

            # Capitalize each word
            name = " ".join(word.capitalize() for word in name_part.split())

            return name

        # Already a name, just return it
        return email_or_name

    def _build_header(self, metadata: dict[str, Any]) -> str:
        """
        Build meeting header with key info

        Args:
            metadata: Meeting metadata

        Returns:
            Header markdown string
        """
        # Parse date/time
        created_at = metadata.get("created_at")
        if created_at:
            try:
                dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                date_formatted = dt.strftime("%A, %B %d, %Y at %I:%M %p")
            except (ValueError, AttributeError):
                date_formatted = "Date unknown"
        else:
            date_formatted = "Date unknown"

        # Build attendee list
        attendees = metadata.get("attendees", [])
        if attendees:
            attendee_links = ", ".join([f"[[{self._extract_name(email)}]]" for email in attendees])
        else:
            attendee_links = "_No attendees recorded_"

        # Build duration
        duration = metadata.get("duration_minutes")
        duration_str = f"{duration} minutes" if duration else "Duration unknown"

        header = f"**{date_formatted}** · {duration_str}  \n**Attendees**: {attendee_links}"

        # Add recording link if available
        recording_url = metadata.get("recording_url")
        meeting_link = metadata.get("meeting_link")

        if recording_url:
            header += f"\n\n🎥 [Recording]({recording_url})"

        if meeting_link:
            header += f" · 📅 [Calendar Event]({meeting_link})"

        return header


if __name__ == "__main__":
    # Test the writer
    import sys

    sys.path.insert(0, "src")
    import json

    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

    print("=== Testing Obsidian Writer ===\n")

    try:
        # Load sample document
        with open("sample_document.json") as f:
            doc = json.load(f)

        # Initialize writer
        cred_manager = CredentialManager()
        writer = ObsidianWriter(cred_manager)

        print(f"Vault path: {writer.vault_path}")
        print(f"Inbox path: {writer.inbox_path}")
        print(f"User: {writer.user_info['name']}")

        # Write meeting note
        print("\nWriting meeting note...")
        filepath = writer.write_meeting_note(doc)

        if filepath:
            print("\n✅ Success! Note created at:")
            print(f"   {filepath}")

            # Show preview
            print("\n=== Note Preview ===")
            with open(filepath) as f:
                content = f.read()
                print(content[:800])
                print("\n[... truncated ...]")
        else:
            print("\n❌ Failed to create note")

    except FileNotFoundError:
        print("❌ sample_document.json not found. Run granola_fetcher.py first.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        logger.exception("Detailed error:")
        sys.exit(1)
