# -*- coding: utf-8 -*-
"""Menu image generator untuk catalog (Pure Python, no pandas required)."""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

log = logging.getLogger(__name__)


def normalize_kategori(kode: str) -> str:
    """Get kategori berdasarkan prefix kode."""
    kategori_map = {
        "SAT_": "🍖 Lauk Satuan",
        "ASIN_": "🐟 Ikan Asin & Lauk Tambahan",
        "SAY_": "🥬 Sayuran",
        "PEL_": "🌶️ Pelengkap",
        "MIN_": "🥤 Minuman",
        "KEM_": "📦 Kemasan",
        "REG_": "🍚 Paket Reguler",
        "KEL_": "👨‍👩‍👧‍👦 Paket Sekeluarga",
        "RAM_": "🌙 Paket Ramadhan",
        "JUK_": "🍲 Paket Combo Jukut",
        "TEH_": "🧋 Paket Es Teh Manis",
        "JER_": "🧃 Paket Es Jeruk",
    }
    for prefix, kategori in kategori_map.items():
        if kode.startswith(prefix):
            return kategori
    return "Lainnya"


def get_kategori_color(kategori: str) -> tuple[int, int, int]:
    """Get RGB color untuk kategori."""
    color_map = {
        "🍖 Lauk Satuan": (255, 107, 107),
        "🐟 Ikan Asin & Lauk Tambahan": (78, 205, 196),
        "🥬 Sayuran": (149, 225, 211),
        "🌶️ Pelengkap": (255, 165, 2),
        "🥤 Minuman": (0, 180, 216),
        "📦 Kemasan": (199, 179, 229),
        "🍚 Paket Reguler": (255, 183, 3),
        "👨‍👩‍👧‍👦 Paket Sekeluarga": (251, 86, 7),
        "🌙 Paket Ramadhan": (131, 56, 236),
        "🍲 Paket Combo Jukut": (255, 190, 11),
        "🧋 Paket Es Teh Manis": (82, 183, 136),
        "🧃 Paket Es Jeruk": (6, 255, 165),
    }
    return color_map.get(kategori, (153, 153, 153))


def format_price(price: int | float | str) -> str:
    """Format harga ke Rupiah."""
    try:
        return f"Rp {int(price):,}".replace(",", ".")
    except (ValueError, TypeError):
        return "Rp 0"


def compute_items_hash(items: list[dict]) -> str:
    """Buat sha256 hash dari items (kode, harga, stok, aktif)."""
    repr_str = "|".join(
        f"{it.get('kode')}:{it.get('harga')}:{it.get('stok')}:{it.get('aktif')}"
        for it in sorted(items, key=lambda x: str(x.get("kode", "")))
    )
    return hashlib.sha256(repr_str.encode("utf-8")).hexdigest()


class MenuGenerator:
    """Generator untuk menu image dari catalog data tanpa dependensi pandas."""

    def __init__(self, output_dir: str = "public", cache_dir: str = "cache"):
        self.output_dir = Path(output_dir)
        self.cache_dir = Path(cache_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.menu_image = self.output_dir / "menu.png"
        self.menu_cache = self.cache_dir / "menu_cache.json"

    def _load_cache(self) -> dict | None:
        """Load cache data."""
        if self.menu_cache.exists():
            try:
                with open(self.menu_cache, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return None
        return None

    def _save_cache(self, items: list[dict]) -> None:
        """Save cache data."""
        cache_data = {
            "hash": compute_items_hash(items),
            "timestamp": datetime.now().isoformat(),
            "count": len(items),
        }
        with open(self.menu_cache, "w", encoding="utf-8") as f:
            json.dump(cache_data, f)

    def _has_changes(self, items: list[dict]) -> bool:
        """Check apakah ada perubahan stok dibanding cache."""
        current_hash = compute_items_hash(items)
        cache = self._load_cache()

        if cache is None:
            return True

        if current_hash != cache.get("hash"):
            log.info("[OK] Stok changes detected")
            return True

        return False

    def generate(self, items: list[dict]) -> bool:
        """Generate gambar menu dari item list.
        
        Args:
            items: List of dicts dengan keys: kode, nama, harga, stok, aktif
            
        Returns:
            True jika image di-generate, False jika tidak ada perubahan atau error
        """
        if not HAS_PIL:
            log.warning("[!] Pillow (PIL) belum terpasang. Gambar menu tidak dapat di-generate.")
            return False

        if not items:
            log.warning("[!] No items to generate")
            return False

        # Filter: stok > 0 dan aktif == TRUE
        filtered: list[dict] = []
        for it in items:
            try:
                stok_val = float(it.get("stok", 0))
            except (ValueError, TypeError):
                stok_val = 0
            
            aktif_val = str(it.get("aktif", "")).strip().upper()
            if stok_val > 0 and aktif_val == "TRUE":
                filtered.append(it)

        if not filtered:
            log.warning("[!] No active items available with stock > 0")
            return False

        log.info(f"[OK] Filtered items: {len(filtered)}")

        # Check changes
        if not self._has_changes(filtered):
            log.info("[i] No changes detected, skipping regeneration")
            return False

        # Group by kategori
        kategori_order = [
            "🍖 Lauk Satuan",
            "🐟 Ikan Asin & Lauk Tambahan",
            "🥬 Sayuran",
            "🌶️ Pelengkap",
            "🥤 Minuman",
            "📦 Kemasan",
            "🍚 Paket Reguler",
            "👨‍👩‍👧‍👦 Paket Sekeluarga",
            "🌙 Paket Ramadhan",
            "🍲 Paket Combo Jukut",
            "🧋 Paket Es Teh Manis",
            "🧃 Paket Es Jeruk",
        ]

        grouped: dict[str, list[dict]] = {kat: [] for kat in kategori_order}
        for it in filtered:
            kat = normalize_kategori(str(it.get("kode", "")))
            if kat not in grouped:
                grouped[kat] = []
            grouped[kat].append(it)

        # Buang kategori yang kosong
        grouped = {k: v for k, v in grouped.items() if v}

        # Generate image
        self._generate_image(grouped)

        # Save cache
        self._save_cache(filtered)

        log.info(f"[OK] Menu image saved: {self.menu_image}")
        return True

    def _generate_image(self, grouped_items: dict[str, list[dict]]) -> None:
        """Generate gambar menu menggunakan PIL murni."""
        total_items = sum(len(items) for items in grouped_items.values())
        total_categories = len(grouped_items)

        # Image dimensions
        img_width = 1200
        img_height = 200 + (total_items * 40) + (total_categories * 50)

        # Create image
        img = Image.new("RGB", (img_width, img_height), color="#F8F9FA")
        draw = ImageDraw.Draw(img)

        # Font setup (fallback ke default jika arial.ttf tidak ada di sistem)
        try:
            title_font = ImageFont.truetype("arial.ttf", 48)
            category_font = ImageFont.truetype("arial.ttf", 24)
            item_font = ImageFont.truetype("arial.ttf", 20)
            price_font = ImageFont.truetype("arial.ttf", 18)
        except Exception:
            title_font = ImageFont.load_default()
            category_font = ImageFont.load_default()
            item_font = ImageFont.load_default()
            price_font = ImageFont.load_default()

        # Header
        draw.rectangle([(0, 0), (img_width, 100)], fill="#2C3E50")
        header_text = "MENU TERSEDIA"
        bbox = draw.textbbox((0, 0), header_text, font=title_font)
        text_width = bbox[2] - bbox[0]
        x_center = (img_width - text_width) // 2
        draw.text((x_center, 25), header_text, fill="#FFFFFF", font=title_font)

        y_position = 120

        # Categories and items
        for kategori, items in grouped_items.items():
            # Category header
            rgb_color = get_kategori_color(kategori)
            draw.rectangle([(20, y_position), (img_width - 20, y_position + 40)], fill=rgb_color)
            draw.text((40, y_position + 8), kategori, fill="#FFFFFF", font=category_font)
            y_position += 50

            # Items
            for idx, item in enumerate(items):
                nama = str(item.get("nama", ""))
                harga = format_price(item.get("harga", 0))

                # Alternating row colors
                if idx % 2 == 0:
                    draw.rectangle([(20, y_position), (img_width - 20, y_position + 38)], fill="#FFFFFF")
                else:
                    draw.rectangle([(20, y_position), (img_width - 20, y_position + 38)], fill="#F0F0F0")

                # Item name
                draw.text((50, y_position + 6), nama, fill="#2C3E50", font=item_font)

                # Price
                draw.text((img_width - 250, y_position + 6), harga, fill="#27AE60", font=price_font)

                # Status
                draw.text((img_width - 120, y_position + 6), "[OK]", fill="#27AE60", font=price_font)

                y_position += 40

            y_position += 10

        # Footer
        footer_text = f"Update: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        draw.text((40, y_position + 20), footer_text, fill="#7F8C8D", font=price_font)

        # Save
        img.save(self.menu_image, quality=95)

    def get_menu_path(self) -> Path | None:
        """Get path ke menu image jika ada."""
        if self.menu_image.exists():
            return self.menu_image
        return None
