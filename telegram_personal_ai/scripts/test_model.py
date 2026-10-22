import asyncio

from app.config import Settings
from app.llm import LlmClient


async def main():
    settings = Settings.from_env()
    client = LlmClient(settings)
    try:
        result = await client.answer(
            "Apa fungsi asisten ini?",
            [{"source": "test", "content": "Asisten membantu membalas saat pemilik sedang sibuk."}],
        )
        print(result)
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
