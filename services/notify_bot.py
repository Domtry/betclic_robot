import httpx
import os

from core.logger import get_logger

log = get_logger("bot.notify")

TELEGRAM_API_URL = os.getenv("TELEGRAM_API_URL")
TELEGRAM_API_KEY = os.getenv("TELEGRAM_API_KEY")
TELEGRAM_BOT_NAME = os.getenv("TELEGRAM_BOT_NAME")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


class TelegramNotifier:
    """Envoie des notifications au bot Telegram via un client HTTP persistant."""

    def __init__(self, chat_id: str, url: str):
        self.url = url
        self.chat_id = chat_id
        self._client = httpx.AsyncClient(timeout=10.0)

    async def envoyer(self, message: str):
        log.info("Envoi de la notification Telegram...")
        await self._client.post(self.url, json={
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "HTML"
        })
        log.info("Notification envoyée")

    async def close(self):
        await self._client.aclose()
        log.debug("Client HTTP Telegram fermé")

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self.close()
