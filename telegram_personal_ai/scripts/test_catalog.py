"""Check the configured catalog without connecting to Telegram or the LLM."""
import asyncio
import logging

from app.catalog import CatalogError, SheetsCatalog
from app.config import Settings


async def main() -> int:
    catalog = SheetsCatalog(Settings.from_env())
    try:
        if not catalog.enabled:
            print("Katalog nonaktif: isi CATALOG_CSV_URL di telegram_personal_ai/.env")
            return 1
        print("Sumber: " + ("CSV publik" if catalog.settings.catalog_csv_url else "API privat"))
        items = await catalog.items()
        print(f"Katalog valid: {len(items)} menu, {sum(item.active for item in items)} aktif.")
        print("Tes jawaban:")
        print(await catalog.answer("daftar menu"))
        return 0
    except CatalogError as exc:
        print(f"Tes gagal: {exc}")
        return 1
    finally:
        await catalog.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    raise SystemExit(asyncio.run(main()))
