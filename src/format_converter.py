"""
Format Converter

Convert Granola's ProseMirror JSON format to Markdown.

ProseMirror structure:
{
  "type": "doc",
  "content": [
    {"type": "heading", "attrs": {"level": 1}, "content": [{"type": "text", "text": "..."}]},
    {"type": "paragraph", "content": [{"type": "text", "text": "...", "marks": [...]}]},
    {"type": "bulletList", "content": [{"type": "listItem", "content": [...]}]},
    ...
  ]
}
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ProseMirrorConverter:
    """Convert ProseMirror JSON to Markdown"""

    def __init__(self):
        self.output_lines = []
        self.list_depth = 0

    def convert(self, prosemirror_doc: dict[str, Any]) -> str:
        """
        Convert ProseMirror document to Markdown

        Args:
            prosemirror_doc: ProseMirror JSON document

        Returns:
            Markdown string
        """
        self.output_lines = []
        self.list_depth = 0

        if not isinstance(prosemirror_doc, dict):
            logger.error("Invalid ProseMirror document: not a dict")
            return ""

        if prosemirror_doc.get("type") != "doc":
            logger.warning(f"Unexpected document type: {prosemirror_doc.get('type')}")

        content = prosemirror_doc.get("content", [])

        for node in content:
            self._convert_node(node)

        # Join lines and clean up extra blank lines
        markdown = "\n".join(self.output_lines)

        # Remove excessive blank lines (more than 2 in a row)
        while "\n\n\n" in markdown:
            markdown = markdown.replace("\n\n\n", "\n\n")

        return markdown.strip()

    def _convert_node(self, node: dict[str, Any], in_list_item: bool = False):
        """
        Convert a single ProseMirror node to Markdown

        Args:
            node: ProseMirror node
            in_list_item: Whether we're inside a list item
        """
        node_type = node.get("type")

        if node_type == "heading":
            self._convert_heading(node)
        elif node_type == "paragraph":
            self._convert_paragraph(node, in_list_item)
        elif node_type == "bulletList":
            self._convert_bullet_list(node)
        elif node_type == "orderedList":
            self._convert_ordered_list(node)
        elif node_type == "codeBlock":
            self._convert_code_block(node)
        elif node_type == "blockquote":
            self._convert_blockquote(node)
        elif node_type == "horizontalRule":
            self.output_lines.append("---")
            self.output_lines.append("")
        elif node_type == "hardBreak":
            self.output_lines.append("")
        else:
            logger.debug(f"Unhandled node type: {node_type}")
            # Try to extract text anyway
            text = self._extract_text(node.get("content", []))
            if text.strip():
                self.output_lines.append(text)

    def _convert_heading(self, node: dict[str, Any]):
        """Convert heading node"""
        level = node.get("attrs", {}).get("level", 1)
        text = self._extract_text(node.get("content", []))

        heading_marker = "#" * level
        self.output_lines.append(f"{heading_marker} {text}")
        self.output_lines.append("")

    def _convert_paragraph(self, node: dict[str, Any], in_list_item: bool = False):
        """Convert paragraph node"""
        text = self._extract_text(node.get("content", []))

        if text.strip():
            if in_list_item:
                # Indent continuation paragraphs in list items
                indent = "  " * self.list_depth
                self.output_lines.append(f"{indent}{text}")
            else:
                self.output_lines.append(text)
                self.output_lines.append("")

    def _convert_bullet_list(self, node: dict[str, Any]):
        """Convert bullet list node"""
        self.list_depth += 1

        for item in node.get("content", []):
            if item.get("type") == "listItem":
                self._convert_list_item(item, bullet="-")

        self.list_depth -= 1

        if self.list_depth == 0:
            self.output_lines.append("")

    def _convert_ordered_list(self, node: dict[str, Any]):
        """Convert ordered list node"""
        self.list_depth += 1

        for i, item in enumerate(node.get("content", []), 1):
            if item.get("type") == "listItem":
                self._convert_list_item(item, bullet=f"{i}.")

        self.list_depth -= 1

        if self.list_depth == 0:
            self.output_lines.append("")

    def _convert_list_item(self, node: dict[str, Any], bullet: str):
        """Convert list item node"""
        indent = "  " * (self.list_depth - 1)
        content_nodes = node.get("content", [])

        if not content_nodes:
            return

        # First node in list item
        first_node = content_nodes[0]

        if first_node.get("type") == "paragraph":
            text = self._extract_text(first_node.get("content", []))
            self.output_lines.append(f"{indent}{bullet} {text}")

            # Handle additional paragraphs or nested lists
            for additional_node in content_nodes[1:]:
                if additional_node.get("type") == "paragraph":
                    self._convert_paragraph(additional_node, in_list_item=True)
                elif additional_node.get("type") in ["bulletList", "orderedList"]:
                    self._convert_node(additional_node)
        else:
            # Not a paragraph, just convert it
            self._convert_node(first_node)

    def _convert_code_block(self, node: dict[str, Any]):
        """Convert code block node"""
        language = node.get("attrs", {}).get("language", "")
        text = self._extract_text(node.get("content", []), preserve_newlines=True)

        self.output_lines.append(f"```{language}")
        self.output_lines.append(text)
        self.output_lines.append("```")
        self.output_lines.append("")

    def _convert_blockquote(self, node: dict[str, Any]):
        """Convert blockquote node"""
        # Convert content and add '> ' prefix
        temp_converter = ProseMirrorConverter()
        temp_converter.output_lines = []

        for content_node in node.get("content", []):
            temp_converter._convert_node(content_node)

        # Add quote markers
        for line in temp_converter.output_lines:
            if line.strip():
                self.output_lines.append(f"> {line}")
            else:
                self.output_lines.append(">")

        self.output_lines.append("")

    def _extract_text(self, content: list[dict[str, Any]], preserve_newlines: bool = False) -> str:
        """
        Recursively extract text from content nodes with formatting

        Args:
            content: List of content nodes
            preserve_newlines: Whether to preserve hard breaks as newlines

        Returns:
            Formatted text string
        """
        if not content:
            return ""

        text_parts = []

        for node in content:
            node_type = node.get("type")

            if node_type == "text":
                text = node.get("text", "")

                # Apply marks (bold, italic, code, etc.)
                marks = node.get("marks", [])
                for mark in marks:
                    mark_type = mark.get("type")

                    if mark_type == "bold":
                        text = f"**{text}**"
                    elif mark_type == "italic":
                        text = f"*{text}*"
                    elif mark_type == "code":
                        text = f"`{text}`"
                    elif mark_type == "strike":
                        text = f"~~{text}~~"
                    elif mark_type == "link":
                        href = mark.get("attrs", {}).get("href", "")
                        text = f"[{text}]({href})"

                text_parts.append(text)

            elif node_type == "hardBreak":
                if preserve_newlines:
                    text_parts.append("\n")
                else:
                    text_parts.append(" ")

            elif "content" in node:
                # Recursively extract from nested content
                nested_text = self._extract_text(node["content"], preserve_newlines)
                text_parts.append(nested_text)

        return "".join(text_parts)


class MetadataExtractor:
    """Extract metadata from Granola document"""

    @staticmethod
    def extract_metadata(doc: dict[str, Any]) -> dict[str, Any]:
        """
        Extract metadata from Granola document

        Args:
            doc: Granola document dictionary

        Returns:
            Dictionary with extracted metadata
        """
        metadata = {
            "granola_id": doc.get("id"),
            "title": doc.get("title", "Untitled Meeting"),
            "created_at": doc.get("created_at"),
            "updated_at": doc.get("updated_at"),
            "type": doc.get("type"),
            "valid_meeting": doc.get("valid_meeting", False),
        }

        # Extract people/attendees
        # People field is a dict with 'creator' and 'attendees' keys
        people = doc.get("people", {})
        attendees = []

        if isinstance(people, dict):
            # Get creator
            creator = people.get("creator", {})
            if isinstance(creator, dict):
                creator_name = creator.get("name") or creator.get("email")
                if creator_name:
                    attendees.append(creator_name)

            # Get attendees list
            attendees_list = people.get("attendees", [])
            for person in attendees_list:
                if isinstance(person, dict):
                    name = person.get("name") or person.get("email")
                    if name:
                        attendees.append(name)
                elif isinstance(person, str):
                    attendees.append(person)

        # Fallback: Try Google Calendar attendees if available
        if not attendees:
            gcal_event = doc.get("google_calendar_event", {})
            gcal_attendees = gcal_event.get("attendees", [])
            for person in gcal_attendees:
                if isinstance(person, dict):
                    name = person.get("displayName") or person.get("email")
                    if name:
                        attendees.append(name)

        metadata["attendees"] = attendees

        # Extract meeting metadata if available
        meeting_metadata = doc.get("metadata", {})
        if meeting_metadata:
            metadata["duration_minutes"] = meeting_metadata.get("duration_minutes")
            metadata["recording_url"] = meeting_metadata.get("recording_url")

        # Extract Google Calendar event info
        gcal_event = doc.get("google_calendar_event")
        if gcal_event:
            metadata["calendar_event_id"] = gcal_event.get("id")
            metadata["meeting_link"] = gcal_event.get("hangoutLink")

        # Extract summary/overview if available
        if doc.get("summary"):
            metadata["summary"] = doc.get("summary")
        elif doc.get("overview"):
            metadata["overview"] = doc.get("overview")

        # Get the actual content from last_viewed_panel
        panel = doc.get("last_viewed_panel")
        if panel:
            metadata["panel_id"] = panel.get("id")
            metadata["panel_title"] = panel.get("title")
            metadata["content"] = panel.get("content")  # ProseMirror JSON

        return metadata


if __name__ == "__main__":
    # Test the converter
    import json
    import sys

    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

    print("=== Testing ProseMirror Converter ===\n")

    # Load sample document
    try:
        with open("sample_document.json") as f:
            doc = json.load(f)

        print("1. Extracting metadata...")
        metadata = MetadataExtractor.extract_metadata(doc)

        print(f"   Title: {metadata['title']}")
        print(f"   Created: {metadata['created_at']}")
        print(f"   Attendees: {len(metadata.get('attendees', []))}")
        print(f"   Has content: {'content' in metadata}")

        if "content" in metadata and metadata["content"]:
            print("\n2. Converting ProseMirror to Markdown...")
            converter = ProseMirrorConverter()
            markdown = converter.convert(metadata["content"])

            print(f"   Converted {len(markdown)} characters")
            print(f"   Lines: {len(markdown.split(chr(10)))}")

            # Save to file
            with open("sample_converted.md", "w") as f:
                f.write(markdown)

            print("\n✅ Saved converted markdown to sample_converted.md")

            # Show preview
            print("\n=== Preview (first 500 chars) ===")
            print(markdown[:500])
            print("...")
        else:
            print("\n❌ No content found in document")

    except FileNotFoundError:
        print("❌ sample_document.json not found. Run granola_fetcher.py first.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        logger.exception("Detailed error:")
        sys.exit(1)
