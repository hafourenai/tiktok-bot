import io
import math
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw, ImageFont
from weather_art import render_weather_art

UTC = timezone.utc

def get_font(size: int, bold: bool = False):
    paths = [
        # Android / Termux system fonts
        "/system/fonts/Roboto-Bold.ttf" if bold else "/system/fonts/Roboto-Regular.ttf",
        "/system/fonts/DroidSans-Bold.ttf" if bold else "/system/fonts/DroidSans.ttf",
        # Linux standard font paths
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        # Windows font paths
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()

def condition_theme(desc: str):
    t = (desc or "").casefold()
    if "petir" in t:
        return ((18, 22, 38), (35, 42, 68), (250, 204, 21))
    if "hujan" in t:
        return ((16, 30, 56), (28, 54, 98), (147, 197, 253))
    if "kabut" in t or "asap" in t:
        return ((35, 42, 52), (58, 69, 84), (209, 213, 219))
    if "cerah berawan" in t:
        return ((18, 52, 98), (42, 96, 172), (253, 224, 71))
    if "berawan" in t:
        return ((24, 34, 48), (42, 55, 75), (226, 232, 240))
    if "cerah" in t:
        return ((14, 68, 140), (32, 110, 180), (254, 215, 102))
    return ((20, 42, 78), (36, 82, 145), (240, 244, 255))

def draw_gradient(draw, width, height, c1, c2):
    for y in range(height):
        r = int(c1[0] + (c2[0] - c1[0]) * (y / height))
        g = int(c1[1] + (c2[1] - c1[1]) * (y / height))
        b = int(c1[2] + (c2[2] - c1[2]) * (y / height))
        draw.line([(0, y), (width, y)], fill=(r, g, b))

def draw_glass(draw, bounds, fill=(255, 255, 255, 24), outline=(255, 255, 255, 48), radius=16):
    draw.rounded_rectangle(bounds, radius=radius, fill=fill, outline=outline, width=1)

def generate_weather_card(data: dict, adm4_code: str, now: datetime = None) -> io.BytesIO:
    now = now or datetime.now(UTC)
    location = data["lokasi"]
    tz_name = location.get("timezone", "Asia/Jakarta")
    labels = {"Asia/Jakarta": "WIB", "Asia/Makassar": "WITA", "Asia/Jayapura": "WIT"}
    tz_label = labels.get(tz_name, "WIB")
    tz = ZoneInfo(tz_name) if tz_name in labels else ZoneInfo("Asia/Jakarta")

    entries = [e for e in data.get("data", []) if e.get("lokasi", {}).get("adm4") == adm4_code]
    if not entries and data.get("data"):
        entries = [data["data"][0]]
    if not entries:
        raise ValueError("Data lokasi cuaca tidak ditemukan")

    rows = []
    for day in entries[0].get("cuaca", []):
        for row in day:
            utc_str = row.get("utc_datetime")
            if utc_str:
                dt = datetime.fromisoformat(utc_str.replace("Z", "+00:00")).replace(tzinfo=UTC)
                rows.append((dt, row))
    rows.sort(key=lambda x: x[0])

    future = [r for r in rows if r[0] >= now]
    if not future and rows:
        future = [rows[-1]]
    if not future:
        raise ValueError("Tidak ada prakiraan cuaca mendatang")

    current_dt, current = future[0]
    desc = current.get("weather_desc", "Cerah Berawan")
    temp = current.get("t", "--")
    humidity = current.get("hu", "--")
    wind_spd = current.get("ws", "--")
    wind_dir = current.get("wd", "--")

    c1, c2, accent = condition_theme(desc)

    WIDTH = 1000
    HEIGHT = 650
    base = Image.new("RGBA", (WIDTH, HEIGHT))
    draw_bg = ImageDraw.Draw(base)
    draw_gradient(draw_bg, WIDTH, HEIGHT, c1, c2)

    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)

    # Ambient glow
    d.ellipse([WIDTH - 320, -100, WIDTH + 220, 420], fill=(255, 255, 255, 18))
    d.ellipse([-160, HEIGHT - 320, 360, HEIGHT + 220], fill=(255, 255, 255, 12))

    # Fonts
    f_badge = get_font(16, bold=True)
    f_loc_main = get_font(34, bold=True)
    f_loc_sub = get_font(20, bold=False)
    f_temp = get_font(88, bold=True)
    f_deg = get_font(44, bold=True)
    f_desc = get_font(26, bold=True)
    f_metric_val = get_font(22, bold=True)
    f_metric_lbl = get_font(15, bold=False)
    f_card_title = get_font(18, bold=True)
    f_timeline_time = get_font(16, bold=True)
    f_timeline_desc = get_font(13, bold=False)
    f_timeline_temp = get_font(20, bold=True)
    f_footer = get_font(14, bold=False)

    # Header Badge
    draw_glass(d, (40, 30, 240, 68), fill=(255, 255, 255, 30), radius=19)
    d.text((62, 39), "BMKG INDONESIA", font=f_badge, fill=(255, 255, 255, 245))

    local_now_str = current_dt.astimezone(tz).strftime("%A, %d %B %Y • %H:%M") + f" {tz_label}"
    d.text((WIDTH - 40, 40), local_now_str, font=f_loc_sub, fill=(240, 240, 255, 220), anchor="ra")

    # Location Information
    loc_title = f"{location.get('desa', '')}, {location.get('kecamatan', '')}"
    loc_subtitle = f"{location.get('kotkab', '')}, {location.get('provinsi', '')}"
    d.text((42, 95), loc_title, font=f_loc_main, fill=(255, 255, 255, 255))
    d.text((43, 142), loc_subtitle, font=f_loc_sub, fill=(215, 230, 250, 220))

    # Hero Card
    draw_glass(d, (40, 185, WIDTH - 40, 385), fill=(255, 255, 255, 22), radius=22)

    # Big vector icon in hero card
    hero_art = render_weather_art(desc, size=110)
    overlay.alpha_composite(hero_art, (65, 205))

    # Temperature & description next to art
    temp_str = str(temp)
    d.text((190, 200), temp_str, font=f_temp, fill=(255, 255, 255, 255))
    deg_x = 190 + (100 if len(temp_str) <= 2 else 145)
    d.text((deg_x, 205), "°C", font=f_deg, fill=(255, 255, 255, 220))
    d.text((195, 312), desc, font=f_desc, fill=accent)

    # Divider
    d.line([(550, 210), (550, 360)], fill=(255, 255, 255, 45), width=1)

    # Right side metrics
    metrics = [
        ("💧  Kelembapan", f"{humidity}%", "Kelembapan Udara"),
        ("💨  Kecepatan Angin", f"{wind_spd} km/j", f"Menuju {wind_dir}"),
        ("🕒  Pembaruan BMKG", current.get("local_datetime", "")[-8:-3] or f"{tz_label}", "Waktu Setempat"),
    ]

    col_x = 585
    for i, (m_title, m_val, m_sub) in enumerate(metrics):
        box_y = 205 + i * 55
        draw_glass(d, (col_x, box_y, WIDTH - 65, box_y + 48), fill=(255, 255, 255, 18), radius=12)
        # Clean title without raw emojis to avoid Windows font box artifacts
        clean_title = m_title.split("  ")[-1]
        # Draw small mini colored circle indicator
        icon_colors = [(96, 165, 250), (147, 197, 253), (250, 204, 21)]
        d.ellipse([col_x + 18, box_y + 18, col_x + 28, box_y + 28], fill=icon_colors[i])
        d.text((col_x + 36, box_y + 13), clean_title, font=f_metric_lbl, fill=(215, 230, 255, 220))
        d.text((WIDTH - 85, box_y + 8), m_val, font=f_metric_val, fill=(255, 255, 255, 255), anchor="ra")
        d.text((WIDTH - 85, box_y + 30), m_sub, font=f_footer, fill=(180, 205, 235, 180), anchor="ra")

    # Timeline Section Header
    d.text((42, 405), "Prakiraan Tiap Periode BMKG", font=f_card_title, fill=(255, 255, 255, 240))

    # 5 upcoming slots
    timeline_items = future[1:6] if len(future) > 1 else future[:1]
    card_count = min(len(timeline_items), 5)
    gap = 14
    total_gap = gap * (card_count - 1)
    card_w = (WIDTH - 80 - total_gap) / card_count

    for idx, (f_dt, f_row) in enumerate(timeline_items):
        cx = int(40 + idx * (card_w + gap))
        cy = 440
        cw = int(card_w)
        ch = 140

        draw_glass(d, (cx, cy, cx + cw, cy + ch), fill=(255, 255, 255, 26), radius=16)

        t_time = f_dt.astimezone(tz).strftime("%H:%M")
        t_desc = f_row.get("weather_desc", "Cerah")
        t_temp = f"{f_row.get('t', '--')}°C"

        d.text((cx + cw // 2, cy + 12), t_time, font=f_timeline_time, fill=(220, 235, 255, 230), anchor="ma")

        # Mini vector art
        mini_art = render_weather_art(t_desc, size=46)
        overlay.alpha_composite(mini_art, (cx + cw // 2 - 23, cy + 34))

        short_desc = t_desc[:12] + ".." if len(t_desc) > 13 else t_desc
        d.text((cx + cw // 2, cy + 86), short_desc, font=f_timeline_desc, fill=(255, 255, 255, 220), anchor="ma")
        d.text((cx + cw // 2, cy + 109), t_temp, font=f_timeline_temp, fill=(255, 255, 255, 255), anchor="ma")

    # Bottom Footer
    d.text((42, 605), "Resmi BMKG • Koordinat terverifikasi wilayah.id & OpenStreetMap", font=f_footer, fill=(255, 255, 255, 160))
    d.text((WIDTH - 42, 605), "Honey Bot Assistant", font=f_footer, fill=(255, 255, 255, 160), anchor="ra")

    final_image = Image.alpha_composite(base, overlay).convert("RGB")
    buf = io.BytesIO()
    final_image.save(buf, format="JPEG", quality=95)
    buf.seek(0)
    return buf
