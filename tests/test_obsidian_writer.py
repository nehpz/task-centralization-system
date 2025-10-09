import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
import yaml
from freezegun import freeze_time

from src.obsidian_writer import ObsidianWriter

# --- Fixtures ---


@pytest.fixture
def mock_cred_manager(tmp_path):
    """Fixture for a mocked CredentialManager."""
    manager = MagicMock()
    manager.get_vault_path.return_value = tmp_path / "TestVault"
    manager.get_user_info.return_value = {"name": "Test User", "email": "test@example.com"}
    return manager


@pytest.fixture
def writer(mock_cred_manager):
    """Fixture for an initialized ObsidianWriter instance."""
    # The writer creates the directory on init, so we need to ensure this runs
    # in a predictable environment.
    return ObsidianWriter(mock_cred_manager)


@pytest.fixture
def sample_metadata():
    """Fixture for a sample metadata dictionary."""
    return {
        "granola_id": "doc_123",
        "title": "Project Kick-off Meeting!",
        "created_at": "2024-08-15T14:30:00Z",
        "attendees": ["Alice Smith <alice@example.com>", "bob.jones@example.com"],
        "duration_minutes": 45,
        "recording_url": "https://recording.com/rec123",
        "meeting_link": "https://meet.com/xyz-abc",
        "summary": "A great meeting.",
    }


# --- Test Cases ---


def test_initialization(writer, mock_cred_manager):
    """Test that the writer initializes correctly and creates the inbox directory."""
    expected_vault_path = mock_cred_manager.get_vault_path()
    expected_inbox_path = expected_vault_path / "00_Inbox" / "Meetings"

    assert writer.vault_path == expected_vault_path
    assert writer.inbox_path == expected_inbox_path
    assert writer.inbox_path.exists()
    assert writer.inbox_path.is_dir()


@pytest.mark.parametrize(
    "input_name, expected_name",
    [
        ("A very/long\\:title with?bad*chars", "A verylongtitle withbadchars"),
        ("  needs trimming  ", "needs trimming"),
        ("lots   of   spaces", "lots of spaces"),
        ("a" * 120, "a" * 100),
    ],
)
def test_sanitize_filename(writer, input_name, expected_name):
    """Test the filename sanitization logic."""
    assert writer._sanitize_filename(input_name) == expected_name


@pytest.mark.parametrize(
    "email_or_name, expected",
    [
        # Standard email-to-name conversions
        ("jane.doe@example.com", "Jane Doe"),
        ("john_smith@work.co.uk", "John Smith"),
        ("test@test.com", "Test"),
        # Plain name string
        ("Already a Name", "Already a Name"),
        # "Name <email>" format
        ("Full Name <full@name.com>", "Full Name"),
        # Edge cases from review
        ("Name With Empty Brackets <>", "Name With Empty Brackets"),
        ("Name With Spaced Brackets < >", "Name With Spaced Brackets"),
        ("  Leading Space <email@test.com>", "Leading Space"),
    ],
)
def test_extract_name_handles_various_formats(writer, email_or_name, expected):
    """Test the extraction of names from various email and name string formats."""
    assert writer._extract_name(email_or_name) == expected


@freeze_time("2024-08-15 10:30:00")
def test_generate_filename(writer, sample_metadata):
    """Test the generation of the note's filename."""
    # With the sanitization fix, the "!" should be removed.
    filename = writer._generate_filename(sample_metadata)
    assert filename == "2024-08-15 - Project Kick-off Meeting.md"

    # Test with missing date using a copy to avoid fixture mutation
    metadata_no_date = sample_metadata.copy()
    del metadata_no_date["created_at"]
    filename_no_date = writer._generate_filename(metadata_no_date)
    assert filename_no_date == "2024-08-15 - Project Kick-off Meeting.md"


def test_build_frontmatter(writer, sample_metadata):
    """Test the YAML frontmatter generation."""
    frontmatter_str = writer._build_frontmatter(sample_metadata)
    frontmatter = yaml.safe_load(frontmatter_str)

    assert frontmatter["date"] == "2024-08-15"
    assert frontmatter["time"] == "14:30"
    assert frontmatter["meeting"] == "Project Kick-off Meeting!"
    assert frontmatter["attendees"] == ["[[Alice Smith]]", "[[Bob Jones]]"]
    assert frontmatter["duration"] == "45 min"
    assert frontmatter["summary"] == "A great meeting."
    assert frontmatter["status"] == "auto-generated"


def test_build_header(writer, sample_metadata):
    """Test the markdown header generation."""
    header = writer._build_header(sample_metadata)
    assert "**Thursday, August 15, 2024 at 02:30 PM**" in header
    assert "[[Alice Smith]], [[Bob Jones]]" in header
    assert "45 minutes" in header
    assert "[Recording](https://recording.com/rec123)" in header
    assert "[Calendar Event](https://meet.com/xyz-abc)" in header


@freeze_time("2024-08-15 11:00:00")
@patch("src.obsidian_writer.MetadataExtractor.extract_metadata")
@patch("src.obsidian_writer.ProseMirrorConverter.convert")
def test_write_meeting_note_success(
    mock_convert, mock_extract, writer, sample_metadata, tmp_path
):
    """Test the full process of writing a meeting note successfully."""
    # --- Setup Mocks ---
    # Add mock content to the metadata to test the conversion path
    metadata_with_content = sample_metadata.copy()
    metadata_with_content["content"] = {"type": "doc", "content": []}
    mock_extract.return_value = metadata_with_content
    mock_convert.return_value = "This is the converted markdown content."

    # --- Execute ---
    doc = {"id": "doc_123"}
    filepath = writer.write_meeting_note(doc)

    # --- Assertions ---
    # Filename should be sanitized
    expected_filename = "2024-08-15 - Project Kick-off Meeting.md"
    expected_path = writer.inbox_path / expected_filename

    assert filepath is not None
    assert filepath == expected_path
    assert filepath.exists()

    content = filepath.read_text()

    # Check that the title in the body is NOT sanitized
    assert "# Project Kick-off Meeting!" in content
    # Check that names are correctly extracted in the header
    assert "Attendees**: [[Alice Smith]], [[Bob Jones]]" in content
    # Check body content
    assert "## Notes" in content
    assert "This is the converted markdown content." in content
    # Check that the converter was called with the right content
    mock_convert.assert_called_once_with(metadata_with_content["content"])
    # Check footer
    assert f"**Granola ID**: `{sample_metadata['granola_id']}`" in content


@patch("src.obsidian_writer.MetadataExtractor.extract_metadata")
@patch("src.obsidian_writer.ProseMirrorConverter.convert")
def test_write_meeting_note_no_content(mock_convert, mock_extract, writer, sample_metadata):
    """Test writing a note when the document has no convertible content."""
    # --- Setup Mocks ---
    # Use a clean copy of the metadata and ensure it has no 'content' key
    metadata_no_content = sample_metadata.copy()
    if "content" in metadata_no_content:
        del metadata_no_content["content"]

    mock_extract.return_value = metadata_no_content

    # --- Execute ---
    doc = {"id": "doc_no_content"}
    filepath = writer.write_meeting_note(doc)
    content = filepath.read_text()

    # --- Assertions ---
    assert filepath is not None
    assert "## Notes" in content
    assert "_No content available_" in content
    # Verify that the converter was NOT called, as there was no content
    mock_convert.assert_not_called()


@patch("src.obsidian_writer.MetadataExtractor.extract_metadata", side_effect=Exception("Extraction failed"))
def test_write_meeting_note_extraction_fails(mock_extract, writer):
    """Test that the function returns None if metadata extraction fails."""
    doc = {"id": "doc_fail"}
    filepath = writer.write_meeting_note(doc)
    assert filepath is None