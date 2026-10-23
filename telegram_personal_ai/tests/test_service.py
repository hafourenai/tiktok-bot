import asyncio
from dataclasses import replace
from pathlib import Path

from app.config import Settings
from app.llm import LlmClient
from app.models import ConversationState
from app.rag import RagEngine
from app.service import AssistantService, AI_FOOTER


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


def test_owner_enables_chat_then_delayed_answer(storage, tmp_path):
    """AI hanya berjalan setelah pemilik mengaktifkan chat dari CLI."""
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

        # Pesan masuk sebelum diaktifkan — tidak diproses
        await service.incoming(1, 1, "Kapan layanan buka?")
        await asyncio.sleep(1.1)
        assert len(sent) == 0

        # Pemilik mengaktifkan dari CLI
        storage.set_chat_enabled(1, True)

        await service.incoming(1, 2, "Kapan layanan buka?")
        await asyncio.sleep(1.1)
        assert len(sent) == 1
        assert "Jawaban berdasarkan dokumen" in sent[0][1]
        assert AI_FOOTER in sent[0][1]
        assert storage.conversation(1)["state"] == ConversationState.AI_ACTIVE
        await service.shutdown()

    asyncio.run(scenario())


def test_user_commands_do_not_activate_ai(storage, tmp_path):
    """Pengguna mengirim /aiaktif — tidak ada efek, AI tetap nonaktif."""
    async def scenario():
        cfg = settings(tmp_path)
        cfg.knowledge_dir.mkdir()
        rag = RagEngine(storage, cfg.knowledge_dir)
        sent = []

        async def sender(chat_id, text):
            sent.append(text)

        service = AssistantService(cfg, storage, rag, FakeLlm(), sender)
        await service.incoming(2, 1, "/aiaktif")
        await service.incoming(2, 2, "/aimati")
        await service.incoming(2, 3, "halo")
        await asyncio.sleep(1.5)
        assert len(sent) == 0
        assert storage.conversation(2)["ai_enabled"] == 0
        await service.shutdown()

    asyncio.run(scenario())


def test_manual_reply_cancels_pending(storage, tmp_path):
    async def scenario():
        cfg = replace(settings(tmp_path), auto_reply_delay=2)
        cfg.knowledge_dir.mkdir()
        rag = RagEngine(storage, cfg.knowledge_dir)
        sent = []

        async def sender(chat_id, text):
            sent.append(text)

        storage.set_chat_enabled(3, True)
        service = AssistantService(cfg, storage, rag, FakeLlm(), sender)
        await service.incoming(3, 1, "Halo")
        service.manual_reply(3)
        await asyncio.sleep(0.05)
        assert len(sent) == 0
        assert storage.conversation(3)["state"] == ConversationState.HUMAN_ACTIVE
        await service.shutdown()

    asyncio.run(scenario())


def test_ai_footer_present_on_all_replies(storage, tmp_path):
    """Setiap balasan AI harus menyertakan penanda footer."""
    async def scenario():
        cfg = settings(tmp_path)
        cfg.knowledge_dir.mkdir()
        (cfg.knowledge_dir / "kb.txt").write_text("Info penting.", encoding="utf-8")
        rag = RagEngine(storage, cfg.knowledge_dir)
        rag.reindex()
        sent = []

        async def sender(chat_id, text):
            sent.append(text)

        storage.set_chat_enabled(4, True)
        service = AssistantService(cfg, storage, rag, FakeLlm(), sender)
        await service.incoming(4, 1, "Apa infonya?")
        await asyncio.sleep(1.1)
        assert sent
        assert AI_FOOTER in sent[-1]
        await service.shutdown()

    asyncio.run(scenario())


def test_disable_chat_stops_ai(storage, tmp_path):
    """Setelah pemilik menonaktifkan, pesan baru tidak diproses."""
    async def scenario():
        cfg = settings(tmp_path)
        cfg.knowledge_dir.mkdir()
        rag = RagEngine(storage, cfg.knowledge_dir)
        sent = []

        async def sender(chat_id, text):
            sent.append(text)

        storage.set_chat_enabled(5, True)
        storage.set_chat_enabled(5, False)
        service = AssistantService(cfg, storage, rag, FakeLlm(), sender)
        await service.incoming(5, 1, "halo")
        await asyncio.sleep(1.5)
        assert len(sent) == 0
        await service.shutdown()

    asyncio.run(scenario())
