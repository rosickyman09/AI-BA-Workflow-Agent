"""Telegram bot integration for backend notifications."""

from __future__ import annotations

import logging
import os
from typing import Optional

from telegram import Bot

logger = logging.getLogger(__name__)


class TelegramBotService:
    """Small wrapper around python-telegram-bot for outbound messages."""

    def __init__(self) -> None:
        self.bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.default_chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")

    def is_configured(self) -> bool:
        return bool(self.bot_token and self.default_chat_id)

    async def send_message(self, message: str, chat_id: Optional[str] = None) -> bool:
        """Send a plain-text Telegram message to target chat."""
        target_chat_id = chat_id or self.default_chat_id
        if not self.bot_token or not target_chat_id:
            logger.info("Telegram not configured - skipping send")
            return False

        try:
            bot = Bot(token=self.bot_token)
            await bot.send_message(chat_id=target_chat_id, text=message)
            return True
        except Exception as exc:
            logger.warning("Failed to send Telegram message: %s", exc)
            return False


telegram_bot_service = TelegramBotService()
