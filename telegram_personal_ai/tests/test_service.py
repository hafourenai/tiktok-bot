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
        spam_window_seconds=60, spam_warn_threshold=5,
    )


def test_new_chat_gets_delayed_answer_without_opt_in(storage, tmp_path):
    """DM baru otomatis diproses tanpa aktivasi per chat."""
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

        await service.incoming(1, 1, "Kapan layanan buka?")
        await asyncio.sleep(1.1)
        assert len(sent) == 1
        assert "Jawaban berdasarkan dokumen" in sent[0][1]
        assert AI_FOOTER in sent[0][1]
        assert sent[0][1].endswith("---\nBalasan Otomatis")
        assert "Sumber:" not in sent[0][1]
        assert "kb.txt" not in sent[0][1]
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
        storage.set_chat_enabled(2, False)
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


def test_manual_reply_pauses_ai_temporarily(storage, tmp_path):
    """Setelah pemilik reply manual, state=HUMAN_ACTIVE tapi ai_enabled tetap 1."""
    async def scenario():
        cfg = settings(tmp_path)
        cfg.knowledge_dir.mkdir()
        (cfg.knowledge_dir / "kb.txt").write_text("Layanan buka hari Senin.", encoding="utf-8")
        rag = RagEngine(storage, cfg.knowledge_dir)
        rag.reindex()
        sent = []

        async def sender(chat_id, text):
            sent.append((chat_id, text))

        storage.set_chat_enabled(6, True)
        service = AssistantService(cfg, storage, rag, FakeLlm(), sender)

        # Pesan pertama masuk
        await service.incoming(6, 1, "Kapan layanan buka?")
        await asyncio.sleep(1.1)
        assert len(sent) == 1

        # Pemilik reply manual
        service.manual_reply(6)
        row = storage.conversation(6)
        assert row["ai_enabled"] == 1  # tetap enabled
        assert row["state"] == ConversationState.HUMAN_ACTIVE

        await service.shutdown()

    asyncio.run(scenario())


def test_auto_resume_on_new_message_after_manual_reply(storage, tmp_path):
    """Pesan baru setelah manual reply auto-resume dan diproses AI."""
    async def scenario():
        cfg = settings(tmp_path)
        cfg.knowledge_dir.mkdir()
        (cfg.knowledge_dir / "kb.txt").write_text("Layanan buka hari Senin.", encoding="utf-8")
        rag = RagEngine(storage, cfg.knowledge_dir)
        rag.reindex()
        sent = []

        async def sender(chat_id, text):
            sent.append((chat_id, text))

        storage.set_chat_enabled(7, True)
        service = AssistantService(cfg, storage, rag, FakeLlm(), sender)

        # Pesan pertama masuk
        await service.incoming(7, 1, "Kapan layanan buka?")
        await asyncio.sleep(1.1)
        assert len(sent) == 1

        # Pemilik reply manual
        service.manual_reply(7)
        assert storage.conversation(7)["state"] == ConversationState.HUMAN_ACTIVE
        sent.clear()

        # Pesan baru masuk — auto-resume dan diproses
        await service.incoming(7, 2, "Hari apa layanan buka?")
        await asyncio.sleep(1.1)
        assert len(sent) == 1
        assert "Jawaban berdasarkan dokumen" in sent[0][1]

        # Pesan ketiga juga diproses (cycle repeat)
        sent.clear()
        service.manual_reply(7)
        await service.incoming(7, 3, "Layanan buka Senin?")
        await asyncio.sleep(1.1)
        assert len(sent) == 1
        assert "Jawaban berdasarkan dokumen" in sent[0][1]

        await service.shutdown()

    asyncio.run(scenario())


def test_spam_rate_limit_sends_acknowledgment(storage, tmp_path):
    """Jika pelanggan kirim 5+ pesan dalam 60 detik, bot kirim acknowledgment sekali."""
    async def scenario():
        cfg = replace(settings(tmp_path), spam_window_seconds=60, spam_warn_threshold=5, auto_reply_delay=1)
        cfg.knowledge_dir.mkdir()
        (cfg.knowledge_dir / "kb.txt").write_text("Info penting.", encoding="utf-8")
        rag = RagEngine(storage, cfg.knowledge_dir)
        rag.reindex()
        sent = []

        async def sender(chat_id, text):
            sent.append((chat_id, text))

        service = AssistantService(cfg, storage, rag, FakeLlm(), sender)

        # Kirim 4 pesan — harus diproses normal (di-buffer dengan debounce)
        await service.incoming(10, 1, "Halo")
        await service.incoming(10, 2, "Halo lagi")
        await service.incoming(10, 3, "Halo lagi lagi")
        await service.incoming(10, 4, "Halo lagi lagi lagi")
        assert len(sent) == 0  # Masih dalam debounce

        # Pesan ke-5 mencapai threshold — kirim acknowledgment
        await service.incoming(10, 5, "Halo ke-5")
        await asyncio.sleep(0.1)
        assert len(sent) == 1
        assert "Pesan kamu sudah kami terima" in sent[0][1]
        assert "akan segera dibalas" in sent[0][1]
        assert AI_FOOTER in sent[0][1]

        await service.shutdown()

    asyncio.run(scenario())


def test_spam_rate_limit_ignores_subsequent_messages(storage, tmp_path):
    """Setelah acknowledgment, pesan berikutnya dalam window diabaikan."""
    async def scenario():
        cfg = replace(settings(tmp_path), spam_window_seconds=60, spam_warn_threshold=3, auto_reply_delay=1)
        cfg.knowledge_dir.mkdir()
        rag = RagEngine(storage, cfg.knowledge_dir)
        sent = []

        async def sender(chat_id, text):
            sent.append(text)

        service = AssistantService(cfg, storage, rag, FakeLlm(), sender)

        # Pesan 1-3 akan memicu acknowledgment
        await service.incoming(11, 1, "A")
        await service.incoming(11, 2, "B")
        await service.incoming(11, 3, "C")
        await asyncio.sleep(0.1)
        assert len(sent) == 1 and "terima" in sent[0]

        # Pesan 4-6 harus diabaikan
        sent.clear()
        await service.incoming(11, 4, "D")
        await service.incoming(11, 5, "E")
        await service.incoming(11, 6, "F")
        await asyncio.sleep(1.2)
        assert len(sent) == 0  # Tidak ada balasan baru

        await service.shutdown()

    asyncio.run(scenario())


def test_spam_rate_limit_window_reset(storage, tmp_path):
    """Window spam direset setelah spam_window_seconds."""
    async def scenario():
        cfg = replace(settings(tmp_path), spam_window_seconds=1, spam_warn_threshold=2, auto_reply_delay=0.5)
        cfg.knowledge_dir.mkdir()
        (cfg.knowledge_dir / "kb.txt").write_text("Jawaban berdasarkan dokumen pengetahuan.", encoding="utf-8")
        rag = RagEngine(storage, cfg.knowledge_dir)
        rag.reindex()
        sent = []

        async def sender(chat_id, text):
            sent.append(text)

        service = AssistantService(cfg, storage, rag, FakeLlm(), sender)

        # Pesan 1-2 dalam window pertama → acknowledgment
        await service.incoming(12, 1, "tanya")
        await service.incoming(12, 2, "tanya")
        await asyncio.sleep(0.1)
        assert len(sent) == 1 and "terima" in sent[0]

        # Tunggu window selesai (1 detik)
        sent.clear()
        await asyncio.sleep(1.1)

        # Pesan baru setelah window reset — diproses normal (tidak spam lagi)
        await service.incoming(12, 3, "apa dokumen pengetahuan?")
        await asyncio.sleep(0.6)
        assert len(sent) == 1 and "Jawaban berdasarkan dokumen" in sent[0]

        await service.shutdown()

    asyncio.run(scenario())
