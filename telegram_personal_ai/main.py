"""Entry point for the Telegram personal AI assistant."""

import asyncio
import logging

from app.config import Settings
from app.telegram_app import TelegramAssistantApp


async def main() -> None:
    settings = Settings.from_env()
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    app = TelegramAssistantApp(settings)
    await app.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
