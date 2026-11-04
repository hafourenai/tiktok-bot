"""Read-only live menu data. Prices and stock never pass through an LLM."""
from __future__ import annotations

import asyncio
import csv
import io
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import quote

import httpx

from .config import Settings

log = logging.getLogger(__name__)


def normalize(text: str) -> str:
    return " ".join(re.findall(r"\w+", text.casefold()))


def commerce_question(text: str) -> bool:
    return bool(set(normalize(text).split()) & {
        "menu", "harga", "harganya", "stok", "stock", "tersedia", "pricelist",
        "paket", "ready", "pesan", "pesen", "porsi", "makanan", "minuman", "menunya", "katalog",
    })


def matches(item: MenuItem, query: str) -> bool:
    name = normalize(item.name)
    short_name = re.sub(r"^(paket|menu)\s+", "", name)
    terms = (name, short_name, normalize(item.code), *item.aliases)
    return any(term and f" {term} " in query for term in terms)


def item_emoji(name: str) -> str:
    norm = normalize(name)
    if any(k in norm for k in ("paket", "combo", "sekeluarga", "ramadhan", "ramadan")):
        return "🍱"
    if any(k in norm for k in ("lele", "nila", "bandeng", "ikan", "peda", "sepat", "jambal", "belah")):
        return "🐟"
    if "ayam" in norm:
        return "🍗"
    if any(k in norm for k in ("es", "teh", "jeruk", "aqua", "minum", "air")):
        return "🥤"
    if any(k in norm for k in ("mie", "mi")):
        return "🍜"
    if any(k in norm for k in ("telor", "telur")):
        return "🍳"
    if any(k in norm for k in ("tahu", "tempe")):
        return "🧈"
    if any(k in norm for k in ("cumi",)):
        return "🦑"
    if any(k in norm for k in ("terong", "pete", "jengkol", "kol", "jukut", "toge", "kangkung", "lalapan")):
        return "🥗"
    if "sambel" in norm or "sambal" in norm:
        return "🌶️"
    if any(k in norm for k in ("packing", "thinwall", "injection", "box", "cup")):
        return "📦"
    return "🍽️"


class CatalogError(Exception):
    pass


@dataclass(frozen=True)
class MenuItem:
    code: str
    name: str
    price: int
    stock: int
    active: bool
    description: str
    aliases: tuple[str, ...]


def parse_items(values: list[list]) -> list[MenuItem]:
    if not values:
        raise CatalogError("Header sheet tidak ditemukan")
    headers = [str(value).strip().lower() for value in values[0]]
    required = {"kode", "nama", "harga", "stok", "aktif", "deskripsi"}
    if not required.issubset(headers) or len(headers) != len(set(headers)):
        raise CatalogError("Header sheet tidak valid")
    items = []
    codes = set()
    for row_number, row in enumerate(values[1:], start=2):
        if not any(str(cell).strip() for cell in row):
            continue
        record = dict(zip(headers, row))
        try:
            code = str(record["kode"]).strip()
            name = str(record["nama"]).strip()
            price = Decimal(str(record["harga"]))
            stock = Decimal(str(record["stok"]))
            active = str(record["aktif"]).strip().lower()
            if (not code or not name or normalize(code) in codes
                    or not price.is_finite() or not stock.is_finite()
                    or price < 0 or stock < 0
                    or price != price.to_integral_value() or stock != stock.to_integral_value()
                    or active not in {"true", "false"}):
                raise ValueError("Nilai katalog tidak valid")
            aliases = tuple(normalize(alias) for alias in str(record.get("alias", "")).split("|")
                            if normalize(alias))
            items.append(MenuItem(code, name, int(price), int(stock), active == "true",
                                  str(record.get("deskripsi", "")).strip(), aliases))
            codes.add(normalize(code))
        except (KeyError, ValueError, InvalidOperation) as exc:
            raise CatalogError(
                f"Baris {row_number} sheet tidak valid; harga/stok harus angka bulat nonnegatif, "
                "kode harus unik, dan aktif harus TRUE/FALSE"
            ) from exc
    return items


class SheetsCatalog:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.enabled = bool(settings.catalog_csv_url or settings.catalog_sheet_id)
        self._http = httpx.AsyncClient(timeout=settings.catalog_timeout)
        self._lock = asyncio.Lock()
        self._credentials = None
        self._items: list[MenuItem] = []
        self._loaded_at: float | None = None
        self._checked_at = ""
        self._checked_time = ""

    def _token(self) -> str:
        # Lazy import: catalog-free installations can still start without Google packages.
        from google.auth.credentials import TokenState
        from google.auth.transport.requests import Request
        from google.oauth2.service_account import Credentials
        import requests

        if not self.settings.catalog_credentials:
            raise CatalogError("GOOGLE_APPLICATION_CREDENTIALS belum diisi")
        if self._credentials is None:
            self._credentials = Credentials.from_service_account_file(
                str(self.settings.catalog_credentials),
                scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
            )
        if self._credentials.token_state != TokenState.FRESH:
            with requests.Session() as session:
                request = Request(session=session)
                self._credentials.refresh(
                    lambda **kwargs: request(**{**kwargs, "timeout": self.settings.catalog_timeout})
                )
        return self._credentials.token

    async def items(self) -> list[MenuItem]:
        async with self._lock:
            if (self._loaded_at is not None
                    and time.monotonic() - self._loaded_at < self.settings.catalog_cache_seconds):
                return self._items
            try:
                if self.settings.catalog_csv_url:
                    # Published Google CSV redirects to googleusercontent.com; no auth is sent.
                    response = await self._http.get(self.settings.catalog_csv_url, follow_redirects=True)
                    response.raise_for_status()
                    values = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig")), strict=True))
                else:
                    token = await asyncio.to_thread(self._token)
                    sheet = quote(self.settings.catalog_sheet_id, safe="")
                    cell_range = quote(self.settings.catalog_sheet_range, safe="")
                    response = await self._http.get(
                        f"https://sheets.googleapis.com/v4/spreadsheets/{sheet}/values/{cell_range}",
                        headers={"Authorization": f"Bearer {token}"},
                        params={"valueRenderOption": "UNFORMATTED_VALUE", "majorDimension": "ROWS"},
                    )
                    response.raise_for_status()
                    values = response.json().get("values", [])
                items = parse_items(values)
            except CatalogError as exc:
                # Our own validation messages contain no cell values, credentials, or URLs.
                log.warning("Katalog tidak tersedia (CatalogError): %s", exc)
                raise
            except Exception as exc:
                # Do not expose token, spreadsheet contents, or credential errors to customers/logs.
                log.warning("Katalog tidak tersedia (%s)", type(exc).__name__)
                raise CatalogError("Katalog tidak dapat diperbarui") from exc
            self._items = items
            self._loaded_at = time.monotonic()
            now_dt = datetime.now().astimezone()
            self._checked_at = now_dt.strftime("%d/%m %H:%M:%S %Z")
            self._checked_time = f"pukul {now_dt.strftime('%H.%M')} WIB"
            return items

    async def answer(self, question: str) -> str | None:
        if not self.enabled:
            return None
        words = set(normalize(question).split())
        if words & {"keluhan", "komplain", "terlambat", "kecewa", "refund", "basi",
                    "ongkir", "alamat", "lokasi", "kebijakan"}:
            return None
        query = f" {normalize(question)} "
        try:
            items = await self.items()
        except CatalogError:
            if commerce_question(question) or any(matches(item, query) for item in self._items):
                return "Maaf kak, harga dan stok terbaru belum dapat diperiksa. Mohon tunggu konfirmasi pemilik ya."
            return None
        matched = [item for item in items if matches(item, query)]
        if not matched and not commerce_question(question):
            return None
        if matched:
            selected = matched
            title = "Menu yang kakak tanyakan"
        else:
            # Generic catalog requests list everything; unknown specific names must not do so.
            generic_words = set("halo hai kak kakak min admin tolong boleh bisa minta lihat tampilkan kasih "
                                "daftar semua seluruh lengkap menu harga harganya berapa ada apa aja saja "
                                "yang dan dengan untuk dong ya nya hari ini sekarang tersedia stok stock "
                                "ready makanan minuman pricelist paket saya aku ingin mau tahu info cek "
                                "kirimin kirim menunya katalog list tanya dong kak".split())
            if set(normalize(question).split()) - generic_words:
                return "Menu tersebut belum ditemukan di katalog. Sebutkan nama menu yang tepat, atau ketik ‘daftar menu’ ya kak."
            selected = [item for item in items if item.active]
            title = "Daftar menu dan harga"
        if not selected:
            return "Saat ini belum ada menu aktif di katalog. Mohon konfirmasi ke pemilik ya kak."
        lines = ["Berikut menu yang tersedia, Kak! 😊", ""]
        for item in selected:
            emoji = item_emoji(item.name)
            price = f"Rp{item.price:,}".replace(",", ".")
            status = (f"Stok tersedia: {item.stock} porsi" if item.active and item.stock > 0
                      else "Stok: Habis" if item.active else "Status: Tidak tersedia")
            lines.append(f"{emoji} **{item.name} — {price}**")
            lines.append(status)
            if item.description:
                desc = item.description
                is_package = any(k in normalize(item.name) for k in ("paket", "combo", "sekeluarga", "ramadhan", "ramadan"))
                if is_package and ("," in desc or "\n" in desc):
                    lines.append("")
                    lines.append("Isi paket:")
                    parts = [p.strip() for p in re.split(r"[,;\n]+", desc) if p.strip()]
                    for part in parts:
                        lines.append(f"- {part}")
                else:
                    lines.append(f"- {desc}")
            lines.append("")
        time_str = self._checked_time or "pukul 10.24 WIB"
        lines.append("Kakak tertarik pesan menu yang mana?")
        lines.append("")
        lines.append(f"_Note: Stok terakhir diperbarui {time_str}. Stok dapat berubah sewaktu-waktu. Pesanan belum dikonfirmasi sebelum proses pemesanan selesai._")
        if matched:
            lines.append("")
            lines.append("_Hanya menu yang cocok di katalog ditampilkan; menu lain yang disebut belum terverifikasi._")
        return "\n".join(lines)

    async def close(self) -> None:
        await self._http.aclose()
