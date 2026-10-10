from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup


def menu_content(section: str):
    back = [InlineKeyboardButton("Kembali ke menu utama", callback_data="menu:home")]
    if section == "downloader":
        text = (
            "<b>Downloader</b>\n\nKirim link TikTok atau YouTube, lalu pilih Biasa atau HD.\n"
            "Status proses akan diperbarui hingga video terkirim.\n\n"
            "<b>Profil TikTok</b>\n/stalk username — lihat profil publik TikTok."
        )
        rows = [back]
    elif section == "discord":
        text = (
            "<b>Discord — Monitoring Voice</b>\n\n"
            "/stats — ringkasan seluruh aktivitas\n/today — rincian hari ini\n"
            "/history 7 — ringkasan 7 hari (1–365 hari)\n\n"
            "<b>Data &amp; penyimpanan</b>\n/export — Excel bulan berjalan\n"
            "/export YYYY-MM — Excel bulan tertentu\n/storage — informasi database\n"
            "/delete YYYY-MM — lihat rincian penghapusan\n"
            "/confirm_delete YYYY-MM — konfirmasi setelah export"
        )
        rows = [
            [InlineKeyboardButton("Statistik", callback_data="action:stats"),
             InlineKeyboardButton("Hari ini", callback_data="action:today")],
            [InlineKeyboardButton("Riwayat 7 hari", callback_data="action:history"),
             InlineKeyboardButton("Export bulan ini", callback_data="action:export")],
            [InlineKeyboardButton("Penyimpanan", callback_data="action:storage")], back,
        ]
    elif section == "cuaca":
        text = (
            "<b>Cuaca Indonesia — BMKG</b>\n\n"
            "/cuaca — minta prakiraan dengan lokasi baru\n"
            "/batal — batalkan permintaan lokasi\n\n"
            "Prakiraan kelurahan/desa dari BMKG, per 3 jam. "
            "Lokasi hanya dipakai untuk satu permintaan."
        )
        rows = [[InlineKeyboardButton("Minta prakiraan", callback_data="action:cuaca")], back]
    else:
        text = "<b>Menu utama</b>\n\nPilih fitur yang ingin digunakan."
        rows = [[InlineKeyboardButton("Downloader", callback_data="menu:downloader"),
                 InlineKeyboardButton("Discord", callback_data="menu:discord")],
                [InlineKeyboardButton("Cuaca", callback_data="menu:cuaca")]]
    return text, InlineKeyboardMarkup(rows)


def menu_commands(section: str):
    commands = [BotCommand("menu", "Kembali ke menu utama")]
    if section == "downloader":
        commands += [BotCommand("stalk", "Lihat profil TikTok")]
    elif section == "discord":
        commands += [BotCommand(name, label) for name, label in [
            ("stats", "Statistik voice"), ("today", "Aktivitas hari ini"),
            ("history", "Riwayat aktivitas"), ("export", "Export Excel"),
            ("storage", "Informasi penyimpanan"), ("delete", "Hapus riwayat"),
            ("confirm_delete", "Konfirmasi hapus riwayat"),
        ]]
    elif section == "cuaca":
        commands += [BotCommand("cuaca", "Prakiraan BMKG dengan lokasi baru"), BotCommand("batal", "Batalkan permintaan lokasi")]
    else:
        commands += [BotCommand("downloader", "Menu Downloader"), BotCommand("discord", "Menu Discord"),
                     BotCommand("cuaca", "Prakiraan cuaca BMKG")]
    return commands + [BotCommand("help", "Bantuan menu aktif")]
