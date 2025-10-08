import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.credential_manager import CredentialManager


@pytest.fixture
def mock_home(monkeypatch, tmp_path: Path):
    """
    Fixture to mock the user's home directory using pytest's temporary directory.
    This makes the test cross-platform and avoids manual cleanup.
    """
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    return tmp_path


@pytest.fixture
def mock_granola_creds_path(mock_home):
    """Fixture to create a mock Granola credentials path."""
    # This path mimics the real location of Granola's credentials
    # but within our controlled mock home directory
    path = mock_home / "Library/Application Support/Granola"
    path.mkdir(parents=True, exist_ok=True)
    return path / "supabase.json"


def test_load_credentials_from_granola_app_success(mock_granola_creds_path):
    """
    Verify that credentials are loaded correctly when a valid
    Granola `supabase.json` file exists.
    """
    # Create a mock `supabase.json` with expected content
    granola_data = {
        "workos_tokens": json.dumps(
            {
                "access_token": "fake_access_token",
                "refresh_token": "fake_refresh_token",
                "expires_at": 1234567890,
            }
        )
    }
    mock_granola_creds_path.write_text(json.dumps(granola_data))

    # Initialize the manager and check if the credentials were loaded
    manager = CredentialManager()
    assert manager.get_granola_token() == "fake_access_token"
    assert manager.credentials["granola"]["refresh_token"] == "fake_refresh_token"


def test_load_credentials_from_granola_app_file_not_found(mock_home):
    """
    Ensure the system handles the absence of the Granola credentials file gracefully
    and returns no token.
    """
    # No credentials file is created for this test
    manager = CredentialManager()
    assert manager.get_granola_token() is None


def test_load_credentials_from_granola_app_malformed_json(mock_granola_creds_path):
    """
    Test the system's resilience to a corrupted or malformed
    Granola `supabase.json` file.
    """
    # Write invalid JSON to the mock file
    mock_granola_creds_path.write_text("this is not json")

    # The manager should handle the error and return no credentials
    manager = CredentialManager()
    assert "granola" not in manager.credentials
    assert manager.get_granola_token() is None


def test_load_credentials_from_granola_app_missing_access_token(mock_granola_creds_path):
    """
    Check that the system correctly handles a valid JSON that is missing
    the essential `access_token`.
    """
    # Create a valid JSON structure but omit the access token
    granola_data = {"workos_tokens": json.dumps({"refresh_token": "fake_refresh_token"})}
    mock_granola_creds_path.write_text(json.dumps(granola_data))

    # The manager should not load the incomplete credentials
    manager = CredentialManager()
    assert "granola" not in manager.credentials
    assert manager.get_granola_token() is None


@pytest.fixture
def mock_config_path(mock_home):
    """Fixture to create a mock custom config path."""
    # This sets up a predictable path for a custom credentials file
    path = mock_home / ".config/task-centralization"
    path.mkdir(parents=True, exist_ok=True)
    return path / "credentials.json"


def test_custom_config_path_loading(mock_config_path):
    """
    Verify that the `CredentialManager` can load credentials from a custom,
    user-specified file path.
    """
    # Create a custom credentials file with specific data
    custom_creds = {"user": {"name": "Custom User"}}
    mock_config_path.write_text(json.dumps(custom_creds))

    # Initialize the manager with the path to our custom file
    manager = CredentialManager(config_path=str(mock_config_path))
    assert manager.get_user_info()["name"] == "Custom User"


def test_credential_merging_logic(mock_granola_creds_path, mock_config_path):
    """
    Ensure that credentials from the Granola app and a custom config file
    are merged correctly, with the custom file taking precedence.
    """
    # Set up Granola credentials, including a user with an email
    granola_data = {
        "workos_tokens": json.dumps({"access_token": "granola_token"}),
        "user": {"name": "Granola User", "email": "granola@example.com"},
    }
    mock_granola_creds_path.write_text(json.dumps(granola_data))

    # Set up a custom config file that overrides the user, but only with a name.
    # The entire 'user' object from Granola should be replaced.
    config_data = {
        "llm": {"provider": "openai", "api_key": "fake_llm_key"},
        "user": {"name": "Config User"},  # This object takes precedence
    }
    mock_config_path.write_text(json.dumps(config_data))

    # Initialize with the custom path to trigger the merge
    manager = CredentialManager(config_path=str(mock_config_path))

    # Verify that data from both sources is present and conflicts are resolved correctly
    assert manager.get_granola_token() == "granola_token"  # From Granola
    assert manager.get_llm_credentials()["provider"] == "openai"  # From config

    # Verify that the user from the config file completely replaced the Granola user
    user_info = manager.get_user_info()
    assert user_info["name"] == "Config User"
    assert "email" not in user_info  # The email from Granola should be gone


def test_get_notion_credentials_success():
    """Test successful retrieval of complete and enabled Notion credentials."""
    creds = {
        "notion": {
            "enabled": True,
            "api_key": "notion_api_key",
            "database_id": "notion_db_id",
        }
    }
    # Patch the internal `credentials` dictionary to simulate loaded data
    with patch.object(CredentialManager, "_load_credentials", return_value=creds):
        manager = CredentialManager()
        notion_creds = manager.get_notion_credentials()
        assert notion_creds["api_key"] == "notion_api_key"
        assert notion_creds["database_id"] == "notion_db_id"


def test_get_notion_credentials_disabled():
    """Ensure that no credentials are returned if Notion is disabled."""
    creds = {"notion": {"enabled": False, "api_key": "key", "database_id": "id"}}
    with patch.object(CredentialManager, "_load_credentials", return_value=creds):
        manager = CredentialManager()
        assert manager.get_notion_credentials() is None


def test_get_notion_credentials_missing():
    """Verify that `None` is returned if Notion credentials are not configured."""
    with patch.object(CredentialManager, "_load_credentials", return_value={}):
        manager = CredentialManager()
        assert manager.get_notion_credentials() is None


def test_get_llm_credentials_incomplete():
    """
    Test that no LLM credentials are returned if the configuration is incomplete
    (e.g., missing the API key).
    """
    creds = {"llm": {"provider": "test_provider"}}  # Missing api_key
    with patch.object(CredentialManager, "_load_credentials", return_value=creds):
        manager = CredentialManager()
        assert manager.get_llm_credentials() is None


def test_default_user_info_and_vault_path(mock_home: Path):
    """
    Check that sensible default values are returned for user info and the vault path
    when they are not specified in any config file.
    """
    with patch.object(CredentialManager, "_load_credentials", return_value={}):
        manager = CredentialManager()
        # Verify default user info
        assert manager.get_user_info() == {"name": "User", "email": "user@example.com"}
        # Verify default vault path, ensuring it uses the mocked home directory
        expected_vault_path = mock_home / "Obsidian" / "zenyth"
        assert manager.get_vault_path() == expected_vault_path


def test_save_credentials(mock_config_path):
    """
    Verify that the `save_credentials` method correctly writes the current
    in-memory credentials to the specified file.
    """
    # Start with an empty manager and manually set some credentials
    manager = CredentialManager(config_path=str(mock_config_path))
    manager.credentials = {"user": {"name": "Saved User"}}

    # Save the credentials
    manager.save_credentials()

    # Read the file back and check its content
    saved_data = json.loads(mock_config_path.read_text())
    assert saved_data["user"]["name"] == "Saved User"


def test_token_refresh_not_implemented():
    """
    Confirm that the token refresh function currently returns `False` as it is
    not yet implemented.
    """
    manager = CredentialManager()
    assert manager.refresh_granola_token() is False