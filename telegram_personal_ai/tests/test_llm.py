import asyncio
import json

import httpx
import pytest

from app.llm import LlmClient
from test_service import settings


@pytest.mark.parametrize("source_line", ["Sumber: layanan.md", "sumber : layanan.md", "**Sumber:** layanan.md"])
def test_no_source_metadata_in_prompt_or_answer(tmp_path, source_line):
    async def scenario():
        def handler(request):
            payload = json.loads(request.content)
            assert "layanan.md" not in payload["messages"][1]["content"]
            return httpx.Response(200, json={"choices": [{"message": {
                "content": "Halo kak, layanan buka Senin 😊\n\n" + source_line,
            }}]})

        llm = LlmClient(settings(tmp_path))
        await llm._http.aclose()
        llm._http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            answer = await llm.answer("Kapan buka?", [{"source": "layanan.md", "content": "Layanan buka Senin."}])
            assert answer == "Halo kak, layanan buka Senin 😊"
        finally:
            await llm.close()
    asyncio.run(scenario())
