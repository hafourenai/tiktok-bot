from __future__ import annotations

import asyncio
import logging

from telethon import TelegramClient, events
from telethon.errors import AuthKeyError, FloodWaitError

from .admin import AdminCli
from .config import Settings
from .llm import LlmClient
from .rag import RagEngine
from .service import AssistantService
from .storage import Storage

log = logging.getLogger(__name__)


class TelegramAssistantApp:
    def __init__(self, settings: Settings):
        self.settings = settings
        settings.session_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage = Storage(settings.database_path)
        self.storage.cancel_all_stale_jobs()
        self.rag = RagEngine(self.storage, settings.knowledge_dir)
        self.llm = LlmClient(settings)
        self.client = TelegramClient(str(settings.session_path), settings.api_id, settings.api_hash)
        self._system_sends: set[int] = set()
        self._system_message_ids: set[tuple[int, int]] = set()
        self.service = AssistantService(settings, self.storage, self.rag, self.llm, self.send_system)
        self.client.add_event_handler(self.on_incoming, events.NewMessage(incoming=True))
        self.client.add_event_handler(self.on_edited, events.MessageEdited(incoming=True))
        self.client.add_event_handler(self.on_deleted, events.MessageDeleted())
        self.client.add_event_handler(self.on_outgoing, events.NewMessage(outgoing=True))

    async def send_system(self, chat_id: int, text: str) -> None:
        self._system_sends.add(chat_id)
        try:
            message = await self.client.send_message(chat_id, text)
            self._system_message_ids.add((chat_id, message.id))
            if len(self._system_message_ids) > 1000:
                self._system_message_ids = set(list(self._system_message_ids)[-500:])
        except FloodWaitError as exc:
            log.warning("Telegram FloodWait %s detik; pesan tidak diulang otomatis", exc.seconds)
            raise
        finally:
            self._system_sends.discard(chat_id)

    async def on_incoming(self, event) -> None:
        if not event.is_private or not event.raw_text or event.chat_id is None:
            return
        sender = await event.get_sender()
        if getattr(sender, "bot", False) or getattr(event.message, "out", False):
            return
        try:
            await self.service.incoming(event.chat_id, event.id, event.raw_text.strip())
        except Exception:
            log.exception("Gagal menangani event masuk chat %s", event.chat_id)

    async def on_outgoing(self, event) -> None:
        if not event.is_private or event.chat_id is None:
            return
        marker = (event.chat_id, event.id)
        if event.chat_id in self._system_sends or marker in self._system_message_ids:
            self._system_message_ids.discard(marker)
            return
        self.service.manual_reply(event.chat_id)

    async def on_edited(self, event) -> None:
        if not event.is_private or not event.raw_text or event.chat_id is None:
            return
        sender = await event.get_sender()
        if not getattr(sender, "bot", False):
            await self.service.incoming(event.chat_id, event.id, event.raw_text.strip())

    async def on_deleted(self, event) -> None:
        if event.chat_id is not None:
            self.service.messages_deleted(event.chat_id, list(event.deleted_ids))

    async def run(self) -> None:
        try:
            await self.client.start()
            me = await self.client.get_me()
            count = self.rag.reindex()
            log.info("Terhubung sebagai account_id=%s; %s chunk knowledge aktif", me.id, count)
            cli_task = None
            if self.settings.admin_cli:
                cli_task = asyncio.create_task(
                    AdminCli(self.storage, self.rag, self.client.disconnect).run()
                )
            await self.client.run_until_disconnected()
            if cli_task:
                cli_task.cancel()
        except AuthKeyError as exc:
            raise RuntimeError("Session Telegram tidak valid atau telah dicabut") from exc
        finally:
            await self.service.shutdown()
            await self.llm.close()
            self.storage.close()
