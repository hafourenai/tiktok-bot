# -*- coding: utf-8 -*-
"""Menu image generator untuk catalog (Pure Python, Termux-ready)."""
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
        "REG_": "🍱 Paket Reguler",
        "KEL_": "👨‍👩‍👧‍👦 Paket Sekeluarga",
        "RAM_": "🌙 Paket Ramadhan",
        "JUK_": "🍲 Paket Combo Jukut",
        "TEH_": "🧋 Paket Combo Es Teh",
        "JER_": "🧃 Paket Combo Es Jeruk",
        "SAT_": "🍗 Lauk Satuan",
        "ASIN_": "🐟 Ikan Asin & Tambahan",
        "SAY_": "🥗 Sayuran",
        "PEL_": "🌶️ Pelengkap & Sambel",
        "MIN_": "🥤 Minuman",
        "KEM_": "📦 Kemasan",
    }
    for prefix, kategori in kategori_map.items():
        if kode.startswith(prefix):
            return kategori
    return "🍽️ Menu Lainnya"


def get_kategori_theme(kategori: str) -> dict:
    """Warna aksen dan background header per kategori."""
    themes = {
        "🍱 Paket Reguler": {"bg": (225, 112, 85), "text": (255, 255, 255)},
        "👨‍👩‍👧‍👦 Paket Sekeluarga": {"bg": (214, 48, 49), "text": (255, 255, 255)},
        "🌙 Paket Ramadhan": {"bg": (108, 92, 231), "text": (255, 255, 255)},
        "🍲 Paket Combo Jukut": {"bg": (230, 126, 34), "text": (255, 255, 255)},
        "🧋 Paket Combo Es Teh": {"bg": (39, 174, 96), "text": (255, 255, 255)},
        "🧃 Paket Combo Es Jeruk": {"bg": (243, 156, 18), "text": (255, 255, 255)},
        "🍗 Lauk Satuan": {"bg": (192, 57, 43), "text": (255, 255, 255)},
        "🐟 Ikan Asin & Tambahan": {"bg": (22, 160, 133), "text": (255, 255, 255)},
        "🥗 Sayuran": {"bg": (46, 204, 113), "text": (255, 255, 255)},
        "🌶️ Pelengkap & Sambel": {"bg": (231, 76, 60), "text": (255, 255, 255)},
        "🥤 Minuman": {"bg": (41, 128, 185), "text": (255, 255, 255)},
        "📦 Kemasan": {"bg": (127, 140, 141), "text": (255, 255, 255)},
    }
    return themes.get(kategori, {"bg": (52, 73, 94), "text": (255, 255, 255)})


def format_price(price: int | float | str) -> str:
    """Format harga ke Rupiah."""
    try:
        return f"Rp {int(price):,}".replace(",", ".")
    except (ValueError, TypeError):
        return "Rp 0"


def compute_items_hash(items: list[dict]) -> str:
    """Buat sha256 hash dari seluruh item (kode, harga, stok, aktif)."""
    repr_str = "|".join(
        f"{it.get('kode')}:{it.get('harga')}:{it.get('stok')}:{it.get('aktif')}"
        for it in sorted(items, key=lambda x: str(x.get("kode", "")))
    )
    return hashlib.sha256(repr_str.encode("utf-8")).hexdigest()


class MenuGenerator:
    """Generator gambar menu modern 2 kolom berbasis Pillow murni."""

    def __init__(self, output_dir: str = "public", cache_dir: str = "cache"):
        self.output_dir = Path(output_dir)
        self.cache_dir = Path(cache_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.menu_image = self.output_dir / "menu.png"
        self.menu_cache = self.cache_dir / "menu_cache.json"

    def _load_cache(self) -> dict | None:
        if self.menu_cache.exists():
            try:
                with open(self.menu_cache, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return None
        return None

    def _save_cache(self, items: list[dict]) -> None:
        cache_data = {
            "hash": compute_items_hash(items),
            "timestamp": datetime.now().isoformat(),
            "count": len(items),
        }
        with open(self.menu_cache, "w", encoding="utf-8") as f:
            json.dump(cache_data, f)

    def _has_changes(self, items: list[dict]) -> bool:
        current_hash = compute_items_hash(items)
        cache = self._load_cache()
        if cache is None or current_hash != cache.get("hash"):
            return True
        return False

    def generate(self, items: list[dict]) -> bool:
        """Filter stok > 0 & aktif == TRUE, lalu buat gambar 2 kolom."""
        if not HAS_PIL:
            log.warning("[!] Pillow belum terpasang. Gambar menu dilewati.")
            return False

        if not items:
            log.warning("[!] Data menu kosong")
            return False

        # Filter stok > 0 dan aktif
        available_items: list[dict] = []
        for it in items:
            try:
                stok_val = float(it.get("stok", 0))
            except (ValueError, TypeError):
                stok_val = 0

            aktif_val = str(it.get("aktif", "")).strip().upper()
            if stok_val > 0 and aktif_val == "TRUE":
                available_items.append(it)

        if not available_items:
            log.warning("[!] Tidak ada menu dengan stok > 0")
            return False

        # Cek perubahan cache
        if not self._has_changes(available_items):
            log.info("[i] Stok tidak berubah, menggunakan gambar menu yang sudah ada")
            return False

        log.info(f"[OK] Membuat gambar menu untuk {len(available_items)} item tersedia...")

        # Kategori terurut logis (Paket-paket dulu di Kolom 1, Satuan/Pelengkap di Kolom 2)
        col1_categories = [
            "🍱 Paket Reguler",
            "👨‍👩‍👧‍👦 Paket Sekeluarga",
            "🌙 Paket Ramadhan",
            "🍲 Paket Combo Jukut",
            "🧋 Paket Combo Es Teh",
            "🧃 Paket Combo Es Jeruk",
        ]
        col2_categories = [
            "🍗 Lauk Satuan",
            "🐟 Ikan Asin & Tambahan",
            "🥗 Sayuran",
            "🌶️ Pelengkap & Sambel",
            "🥤 Minuman",
            "📦 Kemasan",
            "🍽️ Menu Lainnya",
        ]

        grouped: dict[str, list[dict]] = {}
        for it in available_items:
            kat = normalize_kategori(str(it.get("kode", "")))
            if kat not in grouped:
                grouped[kat] = []
            grouped[kat].append(it)

        self._render_image(col1_categories, col2_categories, grouped, len(available_items))
        self._save_cache(available_items)
        log.info(f"[OK] Gambar menu berhasil disimpan: {self.menu_image}")
        return True

    def _render_image(
        self,
        col1_cats: list[str],
        col2_cats: list[str],
        grouped: dict[str, list[dict]],
        total_items: int,
    ) -> None:
        """Render desain menu restoran 2-kolom dengan tipografi modern."""
        width = 1350

        # Hitung tinggi yang dibutuhkan per kolom
        def calc_col_height(cat_list: list[str]) -> int:
            h = 0
            for cat in cat_list:
                items = grouped.get(cat, [])
                if not items:
                    continue
                h += 48  # header kategori
                for item in items:
                    desc = str(item.get("deskripsi", "")).strip()
                    h += 46 if desc else 34
                h += 18  # margin antar kategori
            return h

        h_col1 = calc_col_height(col1_cats)
        h_col2 = calc_col_height(col2_cats)
        content_height = max(h_col1, h_col2)

        header_h = 130
        footer_h = 70
        height = header_h + content_height + footer_h + 40

        img = Image.new("RGB", (width, height), color="#1E272E")  # Dark modern background
        draw = ImageDraw.Draw(img)

        # Muat font
        try:
            font_title = ImageFont.truetype("arial.ttf", 38)
            font_subtitle = ImageFont.truetype("arial.ttf", 16)
            font_cat = ImageFont.truetype("arial.ttf", 20)
            font_item = ImageFont.truetype("arial.ttf", 18)
            font_desc = ImageFont.truetype("arial.ttf", 13)
            font_price = ImageFont.truetype("arial.ttf", 17)
            font_footer = ImageFont.truetype("arial.ttf", 15)
        except Exception:
            font_title = ImageFont.load_default()
            font_subtitle = font_cat = font_item = font_desc = font_price = font_footer = font_title

        # 1. Header Banner
        draw.rectangle([(0, 0), (width, header_h)], fill="#0F141A")
        # Garis aksen emas/oranye di bawah header
        draw.rectangle([(0, header_h - 4), (width, header_h)], fill="#F39C12")

        title_text = "DAFTAR MENU & STOK TERSEDIA"
        t_box = draw.textbbox((0, 0), title_text, font=font_title)
        draw.text(((width - (t_box[2] - t_box[0])) // 2, 28), title_text, fill="#FFFFFF", font=font_title)

        sub_text = f"REALTIME STOCK • {total_items} MENU TERSEDIA • SIAP DIORDER"
        s_box = draw.textbbox((0, 0), sub_text, font=font_subtitle)
        draw.text(((width - (s_box[2] - s_box[0])) // 2, 80), sub_text, fill="#F1C40F", font=font_subtitle)

        # 2. Render Kolom
        col_w = 620
        col1_x = 35
        col2_x = 695
        start_y = header_h + 25

        def render_column(cat_list: list[str], start_x: int) -> None:
            curr_y = start_y
            for cat in cat_list:
                items = grouped.get(cat, [])
                if not items:
                    continue

                theme = get_kategori_theme(cat)

                # Header kategori
                draw.rounded_rectangle(
                    [(start_x, curr_y), (start_x + col_w, curr_y + 36)],
                    radius=6,
                    fill=theme["bg"],
                )
                draw.text((start_x + 14, curr_y + 7), cat, fill=theme["text"], font=font_cat)
                curr_y += 44

                # Daftar Item
                for i, it in enumerate(items):
                    nama = str(it.get("nama", "")).strip()
                    harga = format_price(it.get("harga", 0))
                    desc = str(it.get("deskripsi", "")).strip()

                    row_h = 44 if desc else 32
                    row_bg = "#25303B" if (i % 2 == 0) else "#1F2832"

                    draw.rounded_rectangle(
                        [(start_x, curr_y), (start_x + col_w, curr_y + row_h - 2)],
                        radius=4,
                        fill=row_bg,
                    )

                    # Nama item
                    draw.text((start_x + 12, curr_y + 6), nama, fill="#ECF0F1", font=font_item)

                    # Harga
                    p_box = draw.textbbox((0, 0), harga, font=font_price)
                    pw = p_box[2] - p_box[0]
                    draw.text((start_x + col_w - pw - 14, curr_y + 6), harga, fill="#2ECC71", font=font_price)

                    # Deskripsi / Isi paket
                    if desc:
                        if len(desc) > 68:
                            desc = desc[:65] + "..."
                        draw.text((start_x + 14, curr_y + 26), f"Isi: {desc}", fill="#BDC3C7", font=font_desc)

                    curr_y += row_h

                curr_y += 16  # Jarak antar grup kategori

        render_column(col1_cats, col1_x)
        render_column(col2_cats, col2_x)

        # 3. Footer
        now_str = datetime.now().strftime("%d/%m/%Y pukul %H:%M WIB")
        footer_y = height - footer_h
        draw.rectangle([(0, footer_y), (width, height)], fill="#0F141A")
        draw.rectangle([(0, footer_y), (width, footer_y + 2)], fill="#2C3E50")

        f_text = f"Diperbarui otomatis: {now_str} • Hanya menu berstok aktif yang ditampilkan."
        f_box = draw.textbbox((0, 0), f_text, font=font_footer)
        draw.text(((width - (f_box[2] - f_box[0])) // 2, footer_y + 25), f_text, fill="#95A5A6", font=font_footer)

        # Simpan gambar kualitas tinggi
        img.save(self.menu_image, format="PNG", quality=95)

    def get_menu_path(self) -> Path | None:
        if self.menu_image.exists():
            return self.menu_image
        return None
