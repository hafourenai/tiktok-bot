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


def _draw_scene(image, desc, night, primary, secondary, accent):
    """Draw a quiet illustrated landscape instead of an oversized weather icon."""
    scene = Image.new("RGB", (WIDTH, 695), primary)
    draw = ImageDraw.Draw(scene)
    text = (desc or "").casefold()
    rainy = "hujan" in text or "petir" in text
    hazy = "kabut" in text or "asap" in text
    # A narrow, restrained sky gradient is inexpensive even on Termux.
    for y in range(695):
        blend = y / 694
        color = tuple(round(a * (1 - blend) + b * blend) for a, b in zip(primary, secondary))
        draw.line((0, y, WIDTH, y), fill=color)

    sun_color = (226, 218, 177) if night else (255, 218, 149)
    if rainy:
        sun_color = (175, 204, 208)
    if hazy:
        sun_color = (210, 216, 201)
    draw.ellipse((738, 189, 1028, 479), fill=sun_color)
    # Simple silhouette clouds keep the illustration legible at Telegram size.
    cloud = (118, 154, 163) if rainy else (173, 204, 197) if not night else (87, 119, 136)
    draw.ellipse((715, 350, 871, 405), fill=cloud)
    draw.ellipse((788, 312, 947, 406), fill=cloud)
    draw.rounded_rectangle((734, 365, 1017, 418), radius=26, fill=cloud)
    if rainy:
        for x in range(770, 1010, 48):
            draw.line((x, 438, x - 25, 484), fill=accent, width=5)
    elif night:
        for x, y in ((736, 160), (960, 136), (683, 292)):
            draw.ellipse((x, y, x + 5, y + 5), fill=(236, 229, 192))

    distant = (92, 132, 133) if not night else (46, 81, 99)
    near = (42, 94, 93) if not night else (26, 65, 80)
    draw.polygon([(0, 596), (148, 556), (285, 572), (469, 518), (611, 572),
                  (768, 535), (957, 584), (1080, 549), (1080, 695), (0, 695)], fill=distant)
    draw.polygon([(0, 652), (132, 619), (312, 641), (462, 593), (650, 635),
                  (823, 592), (1080, 635), (1080, 695), (0, 695)], fill=near)
    # Terrace lines evoke an Indonesian landscape without turning the forecast into a map.
    ridge = (116, 157, 139) if not night else (75, 111, 123)
    draw.arc((-74, 633, 521, 753), 187, 348, fill=ridge, width=3)
    draw.arc((427, 616, 1176, 775), 191, 348, fill=ridge, width=3)
    draw.arc((-145, 661, 523, 794), 187, 348, fill=ridge, width=3)
    image.paste(scene, (0, 0))


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

    # Weather as a place: one uninterrupted landscape, not a stack of panels.
    _draw_scene(image, desc, is_night_time(local.hour), primary, secondary, accent)
    white = (255, 255, 255)
    soft = (218, 234, 231)
    _text(draw, (64, 42), "CUACA  /  INDONESIA", 21, soft, bold=True)
    _text(draw, (900, 42), "BMKG", 21, soft, bold=True)
    draw.line((64, 86, 1016, 86), fill=(122, 164, 166), width=2)
    _text(draw, (64, 108), location.get("desa"), 58, white, bold=True, width=950)
    region = ", ".join(str(location.get(key)) for key in ("kecamatan", "kotkab", "provinsi") if location.get(key))
    _text(draw, (64, 177), region or "Indonesia", 25, soft, width=920)
    _text(draw, (46, 232), _value(current.get("t"), "°"), 185, white, bold=True, width=540)
    _text(draw, (64, 439), desc, 42, white, bold=True, width=615)
    _text(draw, (64, 505), f"{local:%d/%m/%Y}    {local:%H:%M} {tz_label}", 27, soft)

    # Deliberately leave a little breathing room between landscape and readings.
    for x in (374, 710):
        draw.line((x, 740, x, 825), fill=RULE, width=2)
    facts = [
        (64, "KELEMBAPAN", _value(current.get("hu"), "%"), 270),
        (410, "KECEPATAN ANGIN", _value(current.get("ws"), " km/j"), 270),
        (746, "ARAH ANGIN", current.get("wd") or "—", 260),
    ]
    for x, label, value, max_width in facts:
        _text(draw, (x, 744), label, 19, MUTED, bold=True)
        _text(draw, (x, 783), value, 34, INK, bold=True, width=max_width)
    draw.line((64, 847, 1016, 847), fill=RULE, width=2)

    _text(draw, (64, 870), "Beberapa jam ke depan", 34, INK, bold=True)
    periods = future[1:5]
    if periods:
        for index, (dt, row) in enumerate(periods):
            x = 64 + index * 242
            column_width = 220 if index == 3 else 225
            if index:
                draw.line((x - 17, 932, x - 17, 1103), fill=RULE, width=2)
            _text(draw, (x, 937), dt.astimezone(tz).strftime("%d/%m  %H:%M"), 20, MUTED, bold=True, width=column_width)
            _paste_art(image, row.get("weather_desc"), (x, 973), 75,
                       is_night=is_night_time(dt.astimezone(tz).hour))
            _text(draw, (x + 82, 990), _value(row.get("t"), "°"), 34, INK, bold=True, width=130)
            _text(draw, (x, 1063), row.get("weather_desc"), 19, MUTED, width=column_width)
    else:
        _text(draw, (64, 959), "Belum ada prakiraan berikutnya.", 26, MUTED)

    draw.line((64, 1121, 1016, 1121), fill=RULE, width=2)
    _text(draw, (64, 1140), "Ringkasan harian", 29, INK, bold=True)
    for index, (label, temp_range, description) in enumerate(
        _daily_summary(future, tz, now.astimezone(tz).date())
    ):
        y = 1196 + index * 39
        _text(draw, (64, y), label, 22, INK, bold=True, width=205)
        _text(draw, (300, y), temp_range, 22, INK, bold=True, width=230)
        _text(draw, (575, y), description, 21, MUTED, width=430)

    draw.line((64, 1304, 1016, 1304), fill=RULE, width=2)
    _text(draw, (64, 1314), "Sumber: BMKG  ·  Prakiraan wilayah", 18, MUTED)
    _text(draw, (822, 1314), "WAKTU " + tz_label, 18, MUTED, bold=True)
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=90)
    buf.seek(0)
    return buf
