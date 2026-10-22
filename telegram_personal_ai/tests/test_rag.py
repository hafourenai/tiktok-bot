from app.rag import RagEngine


def test_reindex_and_retrieve(storage, tmp_path):
    knowledge = tmp_path / "knowledge"
    knowledge.mkdir()
    (knowledge / "harga.md").write_text("Harga layanan dasar adalah lima puluh ribu rupiah.", encoding="utf-8")
    rag = RagEngine(storage, knowledge)
    assert rag.reindex() == 1
    result = rag.search("Berapa harga layanan dasar?")
    assert result
    assert result[0]["source"] == "harga.md"


def test_out_of_context_returns_empty(storage, tmp_path):
    knowledge = tmp_path / "knowledge"
    knowledge.mkdir()
    (knowledge / "info.txt").write_text("Jam buka pukul sembilan.", encoding="utf-8")
    rag = RagEngine(storage, knowledge)
    rag.reindex()
    assert rag.search("Bagaimana cuaca di Mars?") == []
