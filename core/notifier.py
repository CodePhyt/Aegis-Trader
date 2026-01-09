from loguru import logger
import httpx
from plyer import notification
import asyncio

class Notifier:
    def __init__(self, config: dict):
        self.telegram_token = config['system'].get('telegram_token')
        self.telegram_chat_id = config['system'].get('telegram_chat_id')
        self.enable_desktop = config['system'].get('enable_desktop_notifications', True)

    async def send(self, title: str, message: str):
        """
        Send notification to all enabled channels.
        """
        if self.enable_desktop:
            try:
                # Desktop notification is blocking on some OS, run in executor if needed
                # For MVP, plyer is usually fast enough or threaded
                notification.notify(
                    title=f"🦅 Predator: {title}",
                    message=message,
                    app_name="MoonBag Bot",
                    timeout=5
                )
            except Exception as e:
                logger.error(f"Desktop Notify Error: {e}")

        if self.telegram_token and self.telegram_chat_id:
            await self._send_telegram(f"*{title}*\n{message}")

    async def _send_telegram(self, text: str):
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        data = {
            "chat_id": self.telegram_chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }
        try:
            async with httpx.AsyncClient() as client:
                await client.post(url, json=data)
        except Exception as e:
            logger.error(f"Telegram Notify Error: {e}")
