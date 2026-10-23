from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

import httpx

from .config import Settings
from .llm import LlmClient
from .models import ConversationState
from .rag import RagEngine
from .storage import Storage

log = logging.getLogger(__name__)
Sender = Callable[[int, str], Awaitable[None]]

AI_FOOTER = "\n---\nBalasan otomatis AI"


class AssistantService:
    def __init__(
        self, settings: Settings, storage: Storage, rag: RagEngine,
        llm: LlmClient, sender: Sender,
    ):
        self.settings = settings
        self.storage = storage
        self.rag = rag
        self.llm = llm
        self.sender = sender
        self.tasks: dict[int, asyncio.Task] = {}

    async def incoming(self, chat_id: int, message_id: int, text: str) -> None:
        row = self.storage.conversation(chat_id)
        if not row["ai_enabled"]:
            return
        if row["state"] in {ConversationState.HUMAN_ACTIVE, ConversationState.AI_DISABLED}:
            return

        if self.storage.is_duplicate_message(chat_id, message_id, text[: self.settings.max_buffer_chars]):
            return
        self.cancel(chat_id)
        version = self.storage.buffer_message(
            chat_id, message_id, text[: self.settings.max_buffer_chars],
            self.settings.max_buffer_messages,
        )
        delay = self.storage.delay(self.settings.auto_reply_delay)
        execute_at = (datetime.now(UTC) + timedelta(seconds=delay)).isoformat()
        job_id = self.storage.create_job(chat_id, version, execute_at)
        self.tasks[chat_id] = asyncio.create_task(
            self._delayed(chat_id, job_id, version, delay), name=f"reply-{chat_id}"
        )

    def messages_deleted(self, chat_id: int, message_ids: list[int]) -> None:
        if self.storage.delete_messages(chat_id, message_ids):
            self.cancel(chat_id)

    def manual_reply(self, chat_id: int) -> None:
        self.cancel(chat_id)
        self.storage.human_handoff(chat_id)

    def cancel(self, chat_id: int) -> None:
        task = self.tasks.pop(chat_id, None)
        if task and not task.done():
            task.cancel()

    async def _delayed(self, chat_id: int, job_id: str, version: int, delay: int) -> None:
        try:
            await asyncio.sleep(delay)
            if not self.storage.claim_job(job_id, chat_id, version):
                return
            question = self.storage.messages(chat_id, self.settings.max_buffer_chars)
            contexts = self.rag.search(question, self.settings.retrieval_limit)
            if not contexts:
                self.storage.human_handoff(chat_id, "RAG_NO_MATCH")
                await self.sender(
                    chat_id,
                    "Tidak ada informasi yang cocok dalam basis pengetahuan. "
                    "Pesan ini diteruskan kepada pemilik akun." + AI_FOOTER,
                )
                return
            try:
                answer = await self.llm.answer(question, contexts)
                llm_failed = False
            except (httpx.HTTPError, KeyError, ValueError) as exc:
                log.warning("LLM tidak tersedia (%s)", type(exc).__name__)
                llm_failed = True
                answer = "Sistem AI sedang tidak tersedia. Pesan ini diteruskan ke pemilik akun."
            if not self.storage.can_send(job_id, chat_id, version):
                return
            sources = ", ".join(sorted({item["source"] for item in contexts}))
            await self.sender(chat_id, f"{answer}\n\nSumber: {sources}{AI_FOOTER}")
            self.storage.finish_job(job_id, chat_id, True)
            if llm_failed:
                self.storage.human_handoff(chat_id, "LLM_UNAVAILABLE")
        except asyncio.CancelledError:
            return
        except Exception:
            log.exception("Job AI gagal untuk chat %s", chat_id)
            self.storage.finish_job(job_id, chat_id, False)
        finally:
            if self.tasks.get(chat_id) is asyncio.current_task():
                self.tasks.pop(chat_id, None)

    async def shutdown(self) -> None:
        tasks = list(self.tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self.tasks.clear()
