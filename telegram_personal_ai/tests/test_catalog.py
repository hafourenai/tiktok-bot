import asyncio
import csv
import io
from dataclasses import replace

import httpx
import pytest

from app.catalog import CatalogError, SheetsCatalog, parse_items
from app.rag import RagEngine
from app.service import AI_FOOTER, AssistantService
from test_service import settings


VALUES = [
    ["kode", "nama", "harga", "stok", "aktif", "deskripsi", "alias"],
    ["LELE", "Paket Lele", 17300, 12, True, "Nasi, lele, sambal", "lele goreng"],
    ["AYAM", "Paket Ayam", 18000, 0, True, "Nasi, ayam", "ayam goreng"],
    ["BEBEK", "Paket Bebek", 25000, 5, False, "", ""],
]


def make_catalog(tmp_path, handler, ttl=30):
    catalog = SheetsCatalog(replace(settings(tmp_path), catalog_sheet_id="test",
                                   catalog_cache_seconds=ttl))
    # Replace HTTP transport without network calls; token acquisition is tested separately.
    catalog._http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    catalog._token = lambda: "test-token"
    return catalog


def test_listing_specific_multi_unknown_and_faq(tmp_path):
    async def scenario():
        catalog = make_catalog(tmp_path, lambda request: httpx.Response(200, json={"values": VALUES}))
        try:
            full = await catalog.answer("minta daftar harga menu dong")
            assert "Rp17.300" in full and "Paket Ayam" in full
            assert "Paket Bebek" not in full
            one = await catalog.answer("harga lele berapa?")
            assert "Paket Lele" in one and "Paket Ayam" not in one
            multiple = await catalog.answer("Ada lele dan ayam?")
            assert "Paket Lele" in multiple and "Paket Ayam" in multiple and "Stok: Habis" in multiple
            assert "Status: Tidak tersedia" in await catalog.answer("stok bebek")
            assert "belum ditemukan" in await catalog.answer("harga gurame berapa")
            assert await catalog.answer("jam buka kapan?") is None
            assert await catalog.answer("pesanan lele saya terlambat") is None
        finally:
            await catalog.close()
    asyncio.run(scenario())


def test_cache_and_expired_stock_never_used_on_failure(tmp_path):
    async def scenario():
        calls = []
        def handler(request):
            calls.append(request)
            assert request.headers["authorization"] == "Bearer test-token"
            assert request.url.params["valueRenderOption"] == "UNFORMATTED_VALUE"
            if len(calls) > 1:
                return httpx.Response(503)
            return httpx.Response(200, json={"values": VALUES})
        catalog = make_catalog(tmp_path, handler)
        try:
            assert "Stok tersedia" in await catalog.answer("stok lele")
            assert "Stok tersedia" in await catalog.answer("stok lele")
            assert len(calls) == 1
            catalog._loaded_at -= 31
            answer = await catalog.answer("stok lele")
            assert "belum dapat diperiksa" in answer and "Stok tersedia" not in answer
        finally:
            await catalog.close()
    asyncio.run(scenario())


@pytest.mark.parametrize("column,value", [(2, "Rp17.300"), (3, ""), (3, -1),
                                         (3, 1.5), (2, "NaN"), (4, "maybe")])
def test_invalid_rows_fail_closed(column, value):
    values = [row[:] for row in VALUES]
    values[1][column] = value
    with pytest.raises(CatalogError, match="Baris 2 sheet tidak valid"):
        parse_items(values)


def test_short_menu_name_with_nonmatching_code(tmp_path):
    async def scenario():
        values = [row[:] for row in VALUES]
        values[1][0] = "M001"
        catalog = make_catalog(tmp_path, lambda request: httpx.Response(200, json={"values": values}))
        try:
            answer = await catalog.answer("lele berapa?")
            assert "Paket Lele" in answer and "Paket Ayam" not in answer
        finally:
            await catalog.close()
    asyncio.run(scenario())


def test_zero_cache_reads_updated_stock(tmp_path):
    async def scenario():
        values = [row[:] for row in VALUES]
        catalog = make_catalog(tmp_path, lambda request: httpx.Response(200, json={"values": values}), ttl=0)
        try:
            assert "Stok tersedia" in await catalog.answer("stok lele")
            values[1][3] = 0
            assert "Stok: Habis" in await catalog.answer("stok lele")
        finally:
            await catalog.close()
    asyncio.run(scenario())


def test_service_account_uses_readonly_scope_and_bounded_refresh(tmp_path, monkeypatch):
    pytest.importorskip("google.auth")
    from google.auth.credentials import TokenState

    calls = []

    class FakeCredentials:
        token_state = TokenState.INVALID
        token = "refreshed-token"

        def refresh(self, request):
            request(url="https://oauth2.googleapis.com/token", method="POST", body=b"test")
            self.token_state = TokenState.FRESH

    credentials = FakeCredentials()

    def from_file(filename, scopes):
        assert scopes == ["https://www.googleapis.com/auth/spreadsheets.readonly"]
        return credentials

    def request(self, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr("google.oauth2.service_account.Credentials.from_service_account_file", from_file)
    monkeypatch.setattr("google.auth.transport.requests.Request.__call__", request)

    async def scenario():
        cfg = replace(settings(tmp_path), catalog_sheet_id="test",
                      catalog_credentials=tmp_path / "unused.json", catalog_timeout=7)
        catalog = SheetsCatalog(cfg)
        try:
            assert await asyncio.to_thread(catalog._token) == "refreshed-token"
            assert await asyncio.to_thread(catalog._token) == "refreshed-token"
            assert len(calls) == 1 and calls[0]["timeout"] == 7
        finally:
            await catalog.close()
    asyncio.run(scenario())


def test_public_csv_redirect_no_auth_and_priority_over_api(tmp_path):
    async def scenario():
        output = io.StringIO()
        csv.writer(output).writerows(VALUES)
        calls = []
        def handler(request):
            calls.append(request)
            assert "authorization" not in request.headers
            if request.url.host == "docs.google.com":
                return httpx.Response(302, headers={"location": "https://test.googleusercontent.com/menu.csv"})
            return httpx.Response(200, content=("\ufeff" + output.getvalue()).encode("utf-8"))
        cfg = replace(settings(tmp_path), catalog_csv_url="https://docs.google.com/spreadsheets/d/e/test/pub?output=csv",
                      catalog_sheet_id="ignored")
        catalog = SheetsCatalog(cfg)
        await catalog._http.aclose()
        catalog._http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        def no_token():
            raise AssertionError("CSV tidak boleh membutuhkan kredensial Google")
        catalog._token = no_token
        try:
            assert catalog.enabled
            answer = await catalog.answer("harga lele")
            assert "Rp17.300" in answer and "Stok tersedia" in answer
            assert len(calls) == 2
        finally:
            await catalog.close()
    asyncio.run(scenario())


@pytest.mark.parametrize("body", ["", "<html>Access denied</html>", "nama,harga\nLele,17300",
                                  'kode,nama,harga,stok,aktif,deskripsi\nL,Lele,17300,,TRUE,'])
def test_public_csv_empty_or_invalid_fails_safely(tmp_path, body):
    async def scenario():
        cfg = replace(settings(tmp_path), catalog_csv_url="https://docs.google.com/spreadsheets/d/e/test/pub?output=csv")
        catalog = SheetsCatalog(cfg)
        await catalog._http.aclose()
        catalog._http = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, text=body)))
        try:
            answer = await catalog.answer("daftar menu")
            assert "belum dapat diperiksa" in answer
            assert catalog._loaded_at is None
        finally:
            await catalog.close()
    asyncio.run(scenario())


def test_catalog_bypasses_llm_and_rag(storage, tmp_path):
    async def scenario():
        catalog = make_catalog(tmp_path, lambda request: httpx.Response(200, json={"values": VALUES}))
        class NoLlm:
            async def answer(self, *args):
                raise AssertionError("Harga/stok tidak boleh memakai LLM")
        sent = []
        async def sender(chat, text):
            sent.append(text)
        cfg = settings(tmp_path)
        service = AssistantService(cfg, storage, RagEngine(storage, cfg.knowledge_dir),
                                   NoLlm(), sender, catalog)
        try:
            await service.incoming(500, 1, "harga lele berapa")
            await asyncio.sleep(1.1)
            assert len(sent) == 1 and "Rp17.300" in sent[0] and AI_FOOTER in sent[0]
            storage.human_handoff(500, "ADMIN_PAUSED")
            await service.incoming(500, 2, "harga lele")
            assert not service.tasks
        finally:
            await service.shutdown()
            await catalog.close()
    asyncio.run(scenario())
