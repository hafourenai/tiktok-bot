# -*- coding: utf-8 -*-
"""Menu image provider menggunakan kumpulan gambar statis Menu Sambal Joelid."""
from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)


class MenuImageProvider:
    """Mengelola dan menyediakan file gambar menu statis untuk dikirim ke user."""

    def __init__(self, base_dir: Path | str | None = None):
        if base_dir is None:
            # Mengarah ke telegram_personal_ai/
            base_path = Path(__file__).resolve().parents[1]
        else:
            base_path = Path(base_dir)

        # Folder gambar menu
        self.menu_dir = base_path / "public" / "Menu Sambal Joelid-png"

    def get_menu_images(self) -> list[Path]:
        """Ambil ke-6 file gambar menu terurut (1 sampai 6)."""
        if not self.menu_dir.exists():
            log.warning("Folder gambar menu tidak ditemukan: %s", self.menu_dir)
            return []

        # Ambil semua file png dan urutkan berdasarkan nama file
        images = sorted(
            [p for p in self.menu_dir.glob("*.png") if p.is_file()],
            key=lambda x: x.name,
        )

        if not images:
            log.warning("Tidak ada file PNG di %s", self.menu_dir)
            return []

        log.info("Ditemukan %d gambar menu di %s", len(images), self.menu_dir)
        return images
