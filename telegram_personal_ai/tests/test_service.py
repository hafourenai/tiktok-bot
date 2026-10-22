import asyncio
from dataclasses import replace
from pathlib import Path

from app.config import Settings
from app.llm import LlmClient
from app.models import ConversationState
from app.rag import RagEngine
from app.service import AssistantService


class FakeLlm:
    async def answer(self, question, contexts):
        return "Jawaban berdasarkan dokumen."


def settings(tmp_path: Path) -> Settings:
    return Settings(
        api_id=1, api_hash="x", session_path=tmp_path / "s", database_path=tmp_path / "d",
        knowledge_dir=tmp_path / "knowledge", auto_reply_delay=1, max_buffer_messages=5,
        max_buffer_chars=1000, llm_url="http://127.0.0.1:8080/v1/chat/completions",
        llm_model="test", llm_timeout=1, llm_max_tokens=20, llm_temperature=0,
        allow_remote_llm=False, retrieval_limit=3, log_level="INFO", admin_cli=False,
    )


def test_consent_then_delayed_answer(storage, tmp_path):
    async def scenario():
        cfg = settings(tmp_path)
        cfg.knowledge_dir.mkdir()
        (cfg.knowledge_dir / "kb.txt").write_text("Layanan buka hari Senin.", encoding="utf-8")
        rag = RagEngine(storage, cfg.knowledge_dir)
        rag.reindex()
        sent = []

        async def sender(chat_id, text):
            sent.append((chat_id, text))

        service = AssistantService(cfg, storage, rag, FakeLlm(), sender)
        await service.incoming(1, 1, "/aiaktif")
        await service.incoming(1, 2, "Kapan layanan buka?")
        await asyncio.sleep(1.1)
        assert len(sent) == 2
        assert "Jawaban berdasarkan dokumen" in sent[-1][1]
        assert storage.conversation(1)["state"] == ConversationState.AI_ACTIVE
        await service.shutdown()

    asyncio.run(scenario())


def test_manual_reply_cancels_pending(storage, tmp_path):
    async def scenario():
        cfg = replace(settings(tmp_path), auto_reply_delay=2)
        cfg.knowledge_dir.mkdir()
        rag = RagEngine(storage, cfg.knowledge_dir)
        rag.reindex()
        sent = []

        async def sender(chat_id, text):
            sent.append(text)

        service = AssistantService(cfg, storage, rag, FakeLlm(), sender)
        await service.incoming(2, 1, "/aiaktif")
        await service.incoming(2, 2, "Halo")
        service.manual_reply(2)
        await asyncio.sleep(0.05)
        assert len(sent) == 1
        assert storage.conversation(2)["state"] == ConversationState.HUMAN_ACTIVE
        await service.shutdown()

    asyncio.run(scenario())
