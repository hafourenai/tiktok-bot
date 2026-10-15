"""Readable BMKG forecast cards for Telegram, rendered with Pillow."""

import io
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont

from weather_art import render_weather_art


WIDTH, HEIGHT = 1080, 1350
INK = (33, 44, 53)
MUTED = (94, 110, 120)
PAPER = (249, 249, 245)
RULE = (215, 222, 223)


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

    # A single high-contrast header keeps the place, forecast time and condition together.
    draw.rectangle((0, 0, WIDTH, 535), fill=primary)
    draw.rectangle((0, 420, WIDTH, 535), fill=secondary)
    white = (255, 255, 255)
    soft = (213, 231, 231)
    draw.text((64, 48), "PRAKIRAAN CUACA  /  BMKG", font=get_font(25, True), fill=soft)
    draw.text((64, 104), fit_text(draw, location.get("desa"), get_font(57, True), 950), font=get_font(57, True), fill=white)
    region = ", ".join(str(location.get(key) or "") for key in ("kecamatan", "kotkab", "provinsi"))
    draw.text((64, 178), fit_text(draw, region, get_font(26), 950), font=get_font(26), fill=soft)
    draw.line((64, 237, 1016, 237), fill=(114, 151, 157), width=2)

    draw.text((64, 268), "PRAKIRAAN TERDEKAT", font=get_font(22, True), fill=soft)
    draw.text((64, 302), f"{local:%d/%m/%Y}  •  {local:%H:%M} {tz_label}", font=get_font(27), fill=white)
    draw.text((64, 356), fit_text(draw, _value(current.get("t"), "°"), get_font(92, True), 350), font=get_font(92, True), fill=white)
    hero_icon = render_weather_art(desc, size=170)
    image.paste(hero_icon, (815, 263), hero_icon)
    draw.text((64, 455), fit_text(draw, desc, get_font(43, True), 925), font=get_font(43, True), fill=accent)

    # Compact, aligned facts rather than floating icon tiles.
    draw.text((64, 566), "KELEMBAPAN", font=get_font(21, True), fill=MUTED)
    draw.text((64, 602), _value(current.get("hu"), "%"), font=get_font(36, True), fill=INK)
    draw.text((410, 566), "ANGIN", font=get_font(21, True), fill=MUTED)
    draw.text((410, 602), fit_text(draw, _value(current.get("ws"), " km/j"), get_font(32, True), 280), font=get_font(32, True), fill=INK)
    draw.text((795, 566), "ARAH", font=get_font(21, True), fill=MUTED)
    draw.text((795, 602), fit_text(draw, current.get("wd"), get_font(32, True), 215), font=get_font(32, True), fill=INK)
    draw.line((64, 674, 1016, 674), fill=RULE, width=2)

    draw.text((64, 708), "Beberapa jam ke depan", font=get_font(35, True), fill=INK)
    periods = future[1:5]
    for index, (dt, row) in enumerate(periods):
        x = 64 + index * 242
        draw.text((x, 780), dt.astimezone(tz).strftime("%d/%m  %H:%M"), font=get_font(22, True), fill=MUTED)
        icon = render_weather_art(row.get("weather_desc", ""), size=70)
        image.paste(icon, (x, 826), icon)
        draw.text((x, 913), fit_text(draw, row.get("weather_desc"), get_font(21), 215), font=get_font(21), fill=INK)
        draw.text((x, 949), _value(row.get("t"), "°C"), font=get_font(28, True), fill=INK)

    draw.line((64, 1012, 1016, 1012), fill=RULE, width=2)
    draw.text((64, 1045), "Ringkasan harian", font=get_font(35, True), fill=INK)
    days = {}
    for dt, row in future:
        days.setdefault(dt.astimezone(tz).date(), []).append(row)
    for index, (day, periods) in enumerate(list(days.items())[:3]):
        y = 1114 + index * 62
        temps = [row["t"] for row in periods if isinstance(row.get("t"), (float, int))]
        temp_range = f"{min(temps):g}–{max(temps):g}°C" if temps else "—"
        label = "Hari ini" if day == now.astimezone(tz).date() else day.strftime("%d/%m/%Y")
        draw.text((64, y), label, font=get_font(24, True), fill=INK)
        draw.text((300, y), temp_range, font=get_font(24, True), fill=INK)
        description = next((row.get("weather_desc") for row in periods if row.get("weather_desc")), "—")
        draw.text((550, y), fit_text(draw, description, get_font(23), 460), font=get_font(23), fill=MUTED)

    draw.line((64, 1307, 1016, 1307), fill=RULE, width=2)
    draw.text((64, 1320), "Sumber: BMKG  •  Waktu lokal " + tz_label, font=get_font(19), fill=MUTED)
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=90)
    buf.seek(0)
    return buf
