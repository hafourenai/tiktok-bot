from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup


def menu_content(section: str):
    back = [InlineKeyboardButton("🔙 Kembali ke menu utama", callback_data="menu:home")]
    if section == "downloader":
        text = (
            "📥 <b>Media Downloader & Stalker</b>\n\n"
            "• Kirim link <b>TikTok</b> atau <b>YouTube</b> untuk unduh video (pilihan Kualitas Biasa / HD).\n"
            "• Kirim link <b>Instagram</b> (post/reel) untuk unduh foto atau video. Carousel: item pertama saja.\n"
            "• Instagram membutuhkan akun yang dikonfigurasi di server; login dapat terkena verifikasi atau rate limit.\n"
            "• <code>/stalk [username]</code> — intip profil publik TikTok."
        )
        rows = [back]
    elif section == "discord":
        text = (
            "🎙️ <b>Discord Voice Monitor</b>\n\n"
            "Pantau log dan statistik aktivitas channel suara server Discord Anda.\n\n"
            "<b>Perintah Cepat:</b>\n"
            "• <code>/stats</code> — ringkasan total aktivitas\n"
            "• <code>/today</code> — rekap aktivitas hari ini\n"
            "• <code>/history [hari]</code> — riwayat aktivitas (cth: /history 7)\n"
            "• <code>/export</code> — unduh laporan bulanan (Excel .xlsx)\n"
            "• <code>/storage</code> — status penggunaan database"
        )
        rows = [
            [InlineKeyboardButton("📊 Statistik", callback_data="action:stats"),
             InlineKeyboardButton("📅 Hari Ini", callback_data="action:today")],
            [InlineKeyboardButton("📈 Riwayat 7 Hari", callback_data="action:history"),
             InlineKeyboardButton("📑 Export Excel", callback_data="action:export")],
            [InlineKeyboardButton("💾 Info Storage", callback_data="action:storage")],
            back,
        ]
    elif section == "cuaca":
        text = (
            "🌤️ <b>Prakiraan Cuaca Indonesia (BMKG)</b>\n\n"
            "Dapatkan kartu prakiraan cuaca visual resmi BMKG hingga tingkat kelurahan/desa.\n\n"
            "• <b>Via GPS:</b> Tekan tombol di bawah untuk meminta tombol share lokasi.\n"
            "• <b>Via Manual:</b> Pilih provinsi, kota, kecamatan, dan kelurahan secara bertahap.\n"
            "• <code>/batal</code> — batalkan sesi pencarian cuaca kapan saja."
        )
        rows = [
            [InlineKeyboardButton("📍 Kirim Lokasi GPS", callback_data="action:cuaca"),
             InlineKeyboardButton("🏛️ Input Wilayah Manual", callback_data="action:cuaca_manual")],
            back
        ]
    elif section == "converter":
        text = (
            "📑 <b>Document & File Converter Hub</b>\n\n"
            "Konversi berbagai format dokumen secara instan dan rapi!\n\n"
            "<b>Format yang Didukung:</b>\n"
            "• <b>PDF ➔</b> Word (.docx), Excel (.xlsx), PowerPoint (.pptx), Gambar (.png)\n"
            "• <b>Word (.docx) ➔</b> PDF (.pdf)\n"
            "• <b>Excel (.xlsx) ➔</b> PDF (.pdf)\n"
            "• <b>Foto / Gambar (JPG/PNG) ➔</b> PDF (.pdf)\n\n"
            "💡 <i>Cukup kirimkan dokumen/file apa saja ke chat ini, bot akan memberikan tombol pilihan konversi!</i>"
        )
        rows = [back]
    else:
        text = (
            "✨ <b>Menu Utama Honey Assistant</b>\n\n"
            "Silakan pilih layanan yang ingin Anda gunakan:"
        )
        rows = [
            [InlineKeyboardButton("📥 Downloader", callback_data="menu:downloader"),
             InlineKeyboardButton("🎙️ Discord Voice", callback_data="menu:discord")],
            [InlineKeyboardButton("🌤️ Cuaca BMKG", callback_data="menu:cuaca"),
             InlineKeyboardButton("📑 Converter File", callback_data="menu:converter")]
        ]
    return text, InlineKeyboardMarkup(rows)


def menu_commands(section: str):
    commands = [BotCommand("menu", "Menu utama bot")]
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
        commands += [BotCommand("cuaca", "Prakiraan BMKG via GPS"),
                     BotCommand("cuaca_manual", "Prakiraan BMKG via nama wilayah"),
                     BotCommand("batal", "Batalkan sesi cuaca")]
    elif section == "converter":
        commands += [BotCommand("converter", "Panduan konversi dokumen")]
    else:
        commands += [
            BotCommand("downloader", "Menu Downloader"),
            BotCommand("discord", "Menu Discord"),
            BotCommand("cuaca", "Prakiraan cuaca BMKG"),
            BotCommand("converter", "Menu Converter dokumen"),
        ]
    return commands + [BotCommand("help", "Bantuan menu aktif")]
