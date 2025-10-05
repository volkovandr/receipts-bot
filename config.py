"""
Configuration module for receipts bot.
Handles loading and parsing of configuration from config.ini file.
"""

import configparser
import logging
from typing import Set

logger = logging.getLogger(__name__)


class Config:
    """Configuration loader and holder."""

    def __init__(self, config_file: str = 'config.ini'):
        """Load configuration from file."""
        self.config = configparser.ConfigParser()
        self.config.read(config_file)

        # Telegram configuration
        self.telegram_bot_token = self.config.get('telegram', 'bot_token', fallback=None)
        self.allowed_user_ids = self._parse_allowed_user_ids()

        # Database configuration
        self.db_host = self.config.get('database', 'host', fallback='localhost')
        self.db_port = self.config.getint('database', 'port', fallback=5432)
        self.db_name = self.config.get('database', 'name', fallback='receipts_db')
        self.db_user = self.config.get('database', 'user', fallback='')
        self.db_password = self.config.get('database', 'password', fallback='')

        # Anthropic configuration
        self.anthropic_api_key = self.config.get('anthropic', 'api_key', fallback=None)
        self.anthropic_prompt_template = self.config.get('anthropic', 'prompt_template', fallback='prompt-combined.txt')
        self.anthropic_model = self.config.get('anthropic', 'model', fallback='claude-sonnet-4-5-20250929')
        self.anthropic_enable_prompt_caching = self.config.getboolean('anthropic', 'enable_prompt_caching', fallback=False)

    def _parse_allowed_user_ids(self) -> Set[int]:
        """Parse allowed user IDs from config."""
        allowed_ids_str = self.config.get('telegram', 'allowed_user_ids', fallback='')
        if allowed_ids_str:
            return set(int(uid.strip()) for uid in allowed_ids_str.split(',') if uid.strip())
        return set()

    def validate(self) -> bool:
        """Validate required configuration is present."""
        if not self.telegram_bot_token:
            logger.error("TELEGRAM_BOT_TOKEN not found in config.ini file")
            logger.info("Please copy config.ini.example to config.ini and add your bot token")
            return False
        return True
