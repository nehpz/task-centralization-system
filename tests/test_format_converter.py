import pytest

from src.format_converter import ProseMirrorConverter, MetadataExtractor

# --- Tests for ProseMirrorConverter ---


@pytest.fixture
def converter():
    """Returns a fresh instance of ProseMirrorConverter for each test."""
    return ProseMirrorConverter()


def test_convert_empty_document(converter):
    """Test that an empty ProseMirror document results in an empty string."""
    doc = {"type": "doc", "content": []}
    assert converter.convert(doc) == ""


def test_convert_invalid_input(converter):
    """Test that non-dict input is handled gracefully."""
    assert converter.convert(None) == ""
    assert converter.convert("not a dict") == ""


@pytest.mark.parametrize(
    "level, expected_prefix",
    [(1, "#"), (2, "##"), (3, "###"), (4, "####"), (5, "#####"), (6, "######")],
)
def test_convert_headings(converter, level, expected_prefix):
    """Test conversion of headings of all levels."""
    doc = {
        "type": "doc",
        "content": [
            {
                "type": "heading",
                "attrs": {"level": level},
                "content": [{"type": "text", "text": "Test Heading"}],
            }
        ],
    }
    expected_md = f"{expected_prefix} Test Heading"
    assert converter.convert(doc) == expected_md


def test_convert_paragraph(converter):
    """Test conversion of a simple paragraph."""
    doc = {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": "This is a simple paragraph."}],
            }
        ],
    }
    assert converter.convert(doc) == "This is a simple paragraph."


@pytest.mark.parametrize(
    "mark_type, text, expected_md",
    [
        ("bold", "bold text", "**bold text**"),
        ("italic", "italic text", "*italic text*"),
        ("strike", "strikethrough", "~~strikethrough~~"),
        ("code", "inline code", "`inline code`"),
        (
            "link",
            "a link",
            "[a link](https://example.com)",
        ),
    ],
)
def test_convert_text_marks(converter, mark_type, text, expected_md):
    """Test conversion of various text formatting marks."""
    content = {"type": "text", "text": text, "marks": [{"type": mark_type}]}
    # Special case for links, which have attributes
    if mark_type == "link":
        content["marks"][0]["attrs"] = {"href": "https://example.com"}

    doc = {"type": "doc", "content": [{"type": "paragraph", "content": [content]}]}
    assert converter.convert(doc) == expected_md


def test_convert_bullet_list(converter):
    """Test conversion of a simple bullet list."""
    doc = {
        "type": "doc",
        "content": [
            {
                "type": "bulletList",
                "content": [
                    {
                        "type": "listItem",
                        "content": [
                            {"type": "paragraph", "content": [{"type": "text", "text": "Item 1"}]}
                        ],
                    },
                    {
                        "type": "listItem",
                        "content": [
                            {"type": "paragraph", "content": [{"type": "text", "text": "Item 2"}]}
                        ],
                    },
                ],
            }
        ],
    }
    expected_md = "- Item 1\n- Item 2"
    assert converter.convert(doc) == expected_md


def test_convert_ordered_list(converter):
    """Test conversion of a simple ordered list."""
    doc = {
        "type": "doc",
        "content": [
            {
                "type": "orderedList",
                "content": [
                    {
                        "type": "listItem",
                        "content": [
                            {"type": "paragraph", "content": [{"type": "text", "text": "First"}]}
                        ],
                    },
                    {
                        "type": "listItem",
                        "content": [
                            {"type": "paragraph", "content": [{"type": "text", "text": "Second"}]}
                        ],
                    },
                ],
            }
        ],
    }
    expected_md = "1. First\n2. Second"
    assert converter.convert(doc) == expected_md


def test_convert_nested_lists(converter):
    """Test conversion of nested lists."""
    doc = {
        "type": "doc",
        "content": [
            {
                "type": "bulletList",
                "content": [
                    {
                        "type": "listItem",
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [{"type": "text", "text": "Outer 1"}],
                            },
                            {
                                "type": "bulletList",
                                "content": [
                                    {
                                        "type": "listItem",
                                        "content": [
                                            {
                                                "type": "paragraph",
                                                "content": [{"type": "text", "text": "Inner A"}],
                                            }
                                        ],
                                    }
                                ],
                            },
                        ],
                    }
                ],
            }
        ],
    }
    expected_md = "- Outer 1\n  - Inner A"
    assert converter.convert(doc) == expected_md


def test_convert_code_block(converter):
    """Test conversion of a code block with a specified language."""
    doc = {
        "type": "doc",
        "content": [
            {
                "type": "codeBlock",
                "attrs": {"language": "python"},
                "content": [{"type": "text", "text": 'print("Hello, World!")'}],
            }
        ],
    }
    expected_md = '```python\nprint("Hello, World!")\n```'
    assert converter.convert(doc) == expected_md


def test_convert_blockquote(converter):
    """Test conversion of a blockquote."""
    doc = {
        "type": "doc",
        "content": [
            {
                "type": "blockquote",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": "This is a quote."}],
                    }
                ],
            }
        ],
    }
    expected_md = "> This is a quote."
    assert converter.convert(doc) == expected_md


def test_convert_horizontal_rule(converter):
    """Test conversion of a horizontal rule."""
    doc = {"type": "doc", "content": [{"type": "horizontalRule"}]}
    assert converter.convert(doc) == "---"


def test_whitespace_cleanup(converter):
    """Ensure more than two consecutive newlines are collapsed."""
    doc = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "Line 1"}]},
            {"type": "hardBreak"},
            {"type": "hardBreak"},
            {"type": "hardBreak"},
            {"type": "paragraph", "content": [{"type": "text", "text": "Line 2"}]},
        ],
    }
    # A hardBreak creates a newline, and a paragraph adds one after.
    # This test checks if the final cleanup logic works.
    result = converter.convert(doc)
    assert "\n\n\n" not in result
    assert result == "Line 1\n\nLine 2"


# --- Tests for MetadataExtractor ---


def test_extract_metadata_full():
    """Test extraction from a document with all common metadata fields."""
    doc = {
        "id": "doc_123",
        "title": "Test Meeting",
        "created_at": "2024-01-01T12:00:00Z",
        "updated_at": "2024-01-01T13:00:00Z",
        "type": "meeting_notes",
        "valid_meeting": True,
        "people": {
            "creator": {"name": "Alice", "email": "alice@example.com"},
            "attendees": [{"name": "Bob", "email": "bob@example.com"}, "charlie@example.com"],
        },
        "metadata": {"duration_minutes": 60, "recording_url": "https://rec.com/1"},
        "google_calendar_event": {"id": "gcal_456", "hangoutLink": "https://meet.com/1"},
        "last_viewed_panel": {
            "id": "panel_789",
            "title": "Notes",
            "content": {"type": "doc", "content": []},
        },
    }
    metadata = MetadataExtractor.extract_metadata(doc)
    assert metadata["granola_id"] == "doc_123"
    assert metadata["title"] == "Test Meeting"
    assert metadata["attendees"] == ["Alice", "Bob", "charlie@example.com"]
    assert metadata["duration_minutes"] == 60
    assert metadata["meeting_link"] == "https://meet.com/1"
    assert "content" in metadata


def test_extract_metadata_minimal():
    """Test extraction from a minimal document with only essential fields."""
    doc = {"id": "doc_min", "title": "Minimal Meeting"}
    metadata = MetadataExtractor.extract_metadata(doc)
    assert metadata["granola_id"] == "doc_min"
    assert metadata["title"] == "Minimal Meeting"
    assert metadata["attendees"] == []
    assert "duration_minutes" not in metadata
    assert "content" not in metadata


def test_extract_attendees_from_gcal_fallback():
    """Test that attendees are correctly extracted from Google Calendar data as a fallback."""
    doc = {
        "id": "doc_gcal",
        "google_calendar_event": {
            "attendees": [
                {"displayName": "Gcal Alice", "email": "alice@gcal.com"},
                {"email": "bob@gcal.com"}, # No display name
            ]
        },
    }
    metadata = MetadataExtractor.extract_metadata(doc)
    assert metadata["attendees"] == ["Gcal Alice", "bob@gcal.com"]


def test_extract_summary_and_overview():
    """Test that summary and overview fields are correctly identified."""
    doc_summary = {"summary": "This is the summary."}
    meta_summary = MetadataExtractor.extract_metadata(doc_summary)
    assert meta_summary["summary"] == "This is the summary."

    doc_overview = {"overview": "This is the overview."}
    meta_overview = MetadataExtractor.extract_metadata(doc_overview)
    assert meta_overview["overview"] == "This is the overview."