"""
Credential Manager

Securely load and manage credentials for Granola API, Notion API, and LLM services.
"""

import json
import logging
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class CredentialManager:
    """Manage credentials for all integrations"""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize credential manager

        Args:
            config_path: Path to credentials.json (default: ~/.config/task-centralization/credentials.json)
        """
        if config_path:
            self.config_path = Path(config_path).expanduser()
        else:
            self.config_path = Path.home() / ".config" / "task-centralization" / "credentials.json"

        self.credentials = self._load_credentials()

    def _load_credentials(self) -> Dict[str, Any]:
        """
        Load credentials from config file

        Returns:
            Dictionary containing all credentials
        """
        if not self.config_path.exists():
            logger.warning(f"Credentials file not found at: {self.config_path}")
            logger.info("Attempting to load Granola credentials from app storage...")
            return self._load_from_granola_app()

        try:
            with open(self.config_path, 'r') as f:
                creds = json.load(f)
            logger.info(f"Successfully loaded credentials from {self.config_path}")
            return creds
        except Exception as e:
            logger.error(f"Error loading credentials: {str(e)}")
            return {}

    def _load_from_granola_app(self) -> Dict[str, Any]:
        """
        Load Granola credentials directly from app storage

        This is based on Joseph Thacker's approach:
        https://josephthacker.com/hacking/2025/05/08/reverse-engineering-granola-notes.html

        Returns:
            Dictionary with Granola credentials
        """
        granola_creds_path = Path.home() / "Library" / "Application Support" / "Granola" / "supabase.json"

        if not granola_creds_path.exists():
            logger.error(f"Granola credentials not found at: {granola_creds_path}")
            logger.error("Make sure Granola is installed and you've logged in at least once")
            return {}

        try:
            with open(granola_creds_path, 'r') as f:
                data = json.load(f)

            # Parse the workos_tokens string into a dict
            workos_tokens = json.loads(data['workos_tokens'])
            access_token = workos_tokens.get('access_token')
            refresh_token = workos_tokens.get('refresh_token')
            expires_at = workos_tokens.get('expires_at')

            if not access_token:
                logger.error("No access token found in Granola credentials")
                return {}

            logger.info("Successfully loaded Granola credentials from app storage")

            # Return in our standard format
            return {
                "granola": {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "expires_at": expires_at,
                    "source_path": str(granola_creds_path)
                }
            }
        except Exception as e:
            logger.error(f"Error reading Granola credentials: {str(e)}")
            return {}

    def get_granola_token(self) -> Optional[str]:
        """
        Get Granola access token

        Returns:
            Access token string or None if not available
        """
        if "granola" not in self.credentials:
            logger.error("Granola credentials not loaded")
            return None

        access_token = self.credentials["granola"].get("access_token")

        if not access_token:
            logger.error("Granola access token is empty")
            return None

        # TODO: Check if token is expired and refresh if needed
        # expires_at = self.credentials["granola"].get("expires_at")

        return access_token

    def get_notion_credentials(self) -> Optional[Dict[str, str]]:
        """
        Get Notion API credentials

        Returns:
            Dictionary with api_key and database_id, or None if not configured
        """
        if "notion" not in self.credentials:
            logger.debug("Notion credentials not configured")
            return None

        notion_creds = self.credentials["notion"]

        if not notion_creds.get("enabled", False):
            logger.debug("Notion integration is disabled")
            return None

        api_key = notion_creds.get("api_key")
        database_id = notion_creds.get("database_id")

        if not api_key or not database_id:
            logger.error("Notion credentials incomplete (missing api_key or database_id)")
            return None

        return {
            "api_key": api_key,
            "database_id": database_id
        }

    def get_llm_credentials(self) -> Optional[Dict[str, str]]:
        """
        Get LLM API credentials

        Returns:
            Dictionary with provider, api_key, and model, or None if not configured
        """
        if "llm" not in self.credentials:
            logger.error("LLM credentials not configured")
            return None

        llm_creds = self.credentials["llm"]

        provider = llm_creds.get("provider", "claude")
        api_key = llm_creds.get("api_key")
        model = llm_creds.get("model", "claude-3-5-sonnet-20241022")

        if not api_key:
            logger.error("LLM API key not found")
            return None

        return {
            "provider": provider,
            "api_key": api_key,
            "model": model
        }

    def get_user_info(self) -> Dict[str, str]:
        """
        Get user information

        Returns:
            Dictionary with name and email
        """
        if "user" not in self.credentials:
            logger.warning("User info not configured, using defaults")
            return {
                "name": "User",
                "email": "user@example.com"
            }

        return self.credentials["user"]

    def get_vault_path(self) -> Path:
        """
        Get Obsidian vault path

        Returns:
            Path to vault directory
        """
        if "vault" not in self.credentials:
            logger.warning("Vault path not configured, using default")
            return Path.home() / "Obsidian" / "zenyth"

        vault_path = Path(self.credentials["vault"]["path"]).expanduser()
        return vault_path

    def save_credentials(self):
        """
        Save current credentials to config file
        """
        # Create config directory if it doesn't exist
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.credentials, f, indent=2)
            logger.info(f"Credentials saved to {self.config_path}")
        except Exception as e:
            logger.error(f"Error saving credentials: {str(e)}")

    def refresh_granola_token(self) -> bool:
        """
        Refresh Granola access token using refresh token

        TODO: Implement token refresh logic

        Returns:
            True if successful, False otherwise
        """
        logger.warning("Token refresh not yet implemented")
        return False


if __name__ == "__main__":
    # Test credential loading
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    manager = CredentialManager()

    print("\n=== Granola Token ===")
    token = manager.get_granola_token()
    if token:
        print(f"Token: {token[:20]}... (truncated)")
    else:
        print("No token available")

    print("\n=== User Info ===")
    user = manager.get_user_info()
    print(f"Name: {user['name']}")
    print(f"Email: {user['email']}")

    print("\n=== Vault Path ===")
    vault = manager.get_vault_path()
    print(f"Path: {vault}")
    print(f"Exists: {vault.exists()}")
