"""Readable BMKG forecast cards for Telegram, rendered with Pillow."""

import io
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont

from weather_art import render_weather_art


WIDTH, HEIGHT = 1080, 1350
INK = (33, 44, 53)
MUTED = (94, 110, 120)
PAPER = (247, 247, 242)
RULE = (216, 223, 220)


def get_font(size: int, bold: bool = False):
    paths = [
        "/system/fonts/Roboto-Bold.ttf" if bold else "/system/fonts/Roboto-Regular.ttf",
        "/system/fonts/NotoSans-Bold.ttf" if bold else "/system/fonts/NotoSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
    ]
    for path in paths:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, ValueError):
            continue
    return ImageFont.load_default()


def fit_text(draw, text, font, max_width):
    """Keep provider-supplied names and conditions inside their columns."""
    text = str(text or "—")
    if draw.textlength(text, font=font) <= max_width:
        return text
    while text and draw.textlength(text + "…", font=font) > max_width:
        text = text[:-1]
    return text + "…"


def is_night_time(hour: int) -> bool:
    return hour >= 18 or hour < 6


def condition_theme(desc: str, is_night: bool = False):
    """Return header, secondary header and highlight colors."""
    text = (desc or "").casefold()
    if "petir" in text:
        return (34, 48, 63), (50, 68, 78), (255, 211, 120)
    if "hujan" in text:
        return (31, 65, 83), (44, 88, 105), (184, 224, 239)
    if is_night:
        return (18, 32, 45), (35, 52, 66), (228, 220, 173)
    if "cerah" in text:
        return (34, 84, 104), (47, 108, 118), (255, 216, 147)
    return (44, 69, 78), (60, 87, 93), (213, 231, 226)


def _value(value, unit=""):
    if value is None or value == "":
        return "—"
    if isinstance(value, (float, int)):
        value = f"{value:g}"
    return f"{value}{unit}"


def _forecast_rows(data, adm4_code):
    entries = [entry for entry in data.get("data", []) if entry.get("lokasi", {}).get("adm4") == adm4_code]
    if not entries:
        raise ValueError("Data lokasi cuaca tidak ditemukan")
    rows = []
    for day in entries[0].get("cuaca", []):
        for row in day:
            timestamp = row.get("utc_datetime")
            if not timestamp:
                continue
            try:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except ValueError:
                continue
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            rows.append((dt.astimezone(timezone.utc), row))
    return sorted(rows, key=lambda item: item[0])


def _paste_art(image, desc, position, size, *, is_night=False):
    art = render_weather_art(desc or "", size=size, is_night=is_night)
    image.paste(art, position, art)


def _text(draw, xy, value, size, color, *, bold=False, width=None):
    font = get_font(size, bold)
    label = fit_text(draw, value, font, width) if width is not None else str(value)
    draw.text(xy, label, font=font, fill=color)


def _daily_summary(future, tz, today):
    days = {}
    for dt, row in future:
        days.setdefault(dt.astimezone(tz).date(), []).append(row)
    result = []
    for day, periods in list(days.items())[:3]:
        temps = [row["t"] for row in periods if isinstance(row.get("t"), (float, int)) and not isinstance(row["t"], bool)]
        temp_range = f"{min(temps):g}–{max(temps):g}°" if temps else "—"
        label = "Hari ini" if day == today else day.strftime("%d/%m")
        description = next((row.get("weather_desc") for row in periods if row.get("weather_desc")), "—")
        result.append((label, temp_range, description))
    return result


def generate_weather_card(data: dict, adm4_code: str, now: datetime = None) -> io.BytesIO:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    location = data["lokasi"]
    tz_name = location.get("timezone", "Asia/Jakarta")
    labels = {"Asia/Jakarta": "WIB", "Asia/Makassar": "WITA", "Asia/Jayapura": "WIT"}
    tz = ZoneInfo(tz_name if tz_name in labels else "Asia/Jakarta")
    tz_label = labels.get(tz_name, "WIB")

    rows = _forecast_rows(data, adm4_code)
    future = [(dt, row) for dt, row in rows if dt >= now]
    if not future and rows:
        future = [rows[-1]]
    if not future:
        raise ValueError("Tidak ada prakiraan cuaca mendatang")

    current_dt, current = future[0]
    local = current_dt.astimezone(tz)
    desc = current.get("weather_desc") or "Tidak tersedia"
    primary, secondary, accent = condition_theme(desc, is_night_time(local.hour))
    image = Image.new("RGB", (WIDTH, HEIGHT), PAPER)
    draw = ImageDraw.Draw(image)

    # An editorial-style hero: location above a single large reading and illustration.
    draw.rectangle((0, 0, WIDTH, 570), fill=primary)
    draw.ellipse((675, 150, 1070, 522), fill=secondary)
    draw.ellipse((719, 188, 1026, 496), outline=(102, 146, 150), width=2)
    draw.rectangle((0, 524, WIDTH, 570), fill=secondary)
    white = (255, 255, 255)
    soft = (218, 234, 231)
    _text(draw, (64, 40), "BMKG  /  PRAKIRAAN CUACA", 22, soft, bold=True)
    _text(draw, (64, 95), location.get("desa"), 59, white, bold=True, width=946)
    region = ", ".join(str(location.get(key)) for key in ("kecamatan", "kotkab", "provinsi") if location.get(key))
    _text(draw, (64, 170), region or "Indonesia", 26, soft, width=930)
    draw.line((64, 234, 1016, 234), fill=(126, 166, 165), width=2)

    _text(draw, (64, 262), f"{local:%d/%m/%Y}  ·  {local:%H:%M} {tz_label}", 27, soft)
    _text(draw, (50, 307), _value(current.get("t"), "°"), 160, white, bold=True, width=540)
    _paste_art(image, desc, (700, 287), 240, is_night=is_night_time(local.hour))
    _text(draw, (64, 528), desc, 29, accent, bold=True, width=940)

    # One quiet information band instead of three framed cards.
    for x in (374, 710):
        draw.line((x, 600, x, 693), fill=RULE, width=2)
    facts = [
        (64, "KELEMBAPAN", _value(current.get("hu"), "%"), 270),
        (410, "KECEPATAN ANGIN", _value(current.get("ws"), " km/j"), 270),
        (746, "ARAH ANGIN", current.get("wd") or "—", 260),
    ]
    for x, label, value, max_width in facts:
        _text(draw, (x, 603), label, 20, MUTED, bold=True)
        _text(draw, (x, 645), value, 34, INK, bold=True, width=max_width)
    draw.line((64, 729, 1016, 729), fill=RULE, width=2)

    _text(draw, (64, 757), "Beberapa jam ke depan", 35, INK, bold=True)
    periods = future[1:5]
    if periods:
        draw.line((108, 865, 971, 865), fill=RULE, width=4)
        for index, (dt, row) in enumerate(periods):
            x = 64 + index * 242
            column_width = 220 if index == 3 else 225
            _text(draw, (x, 815), dt.astimezone(tz).strftime("%d/%m  %H:%M"), 22, MUTED, bold=True, width=column_width)
            draw.ellipse((x + 33, 858, x + 47, 872), fill=primary)
            _paste_art(image, row.get("weather_desc"), (x + 2, 884), 82,
                       is_night=is_night_time(dt.astimezone(tz).hour))
            _text(draw, (x, 973), _value(row.get("t"), "°C"), 32, INK, bold=True, width=column_width)
            _text(draw, (x, 1020), row.get("weather_desc"), 20, MUTED, width=column_width)
    else:
        _text(draw, (64, 858), "Belum ada prakiraan berikutnya.", 26, MUTED)

    draw.line((64, 1086, 1016, 1086), fill=RULE, width=2)
    _text(draw, (64, 1110), "Ringkasan harian", 32, INK, bold=True)
    for index, (label, temp_range, description) in enumerate(
        _daily_summary(future, tz, now.astimezone(tz).date())
    ):
        y = 1172 + index * 48
        _text(draw, (64, y), label, 22, INK, bold=True, width=205)
        _text(draw, (300, y), temp_range, 22, INK, bold=True, width=230)
        _text(draw, (575, y), description, 21, MUTED, width=430)

    draw.line((64, 1311, 1016, 1311), fill=RULE, width=2)
    _text(draw, (64, 1320), "Sumber data: BMKG", 18, MUTED)
    _text(draw, (822, 1320), "WAKTU " + tz_label, 18, MUTED, bold=True)
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=90)
    buf.seek(0)
    return buf
