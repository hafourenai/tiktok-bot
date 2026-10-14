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

def condition_theme(desc: str, is_night: bool = False):
    """Returns (bg_top, bg_bottom, accent_color) based on weather condition and time of day."""
    t = (desc or "").casefold()
    
    if is_night:
        # Night themes
        if "petir" in t:
            return ((10, 12, 25), (20, 25, 45), (250, 200, 50))
        if "hujan" in t:
            return ((8, 18, 40), (15, 35, 65), (130, 180, 255))
        if "kabut" in t or "asap" in t:
            return ((25, 28, 38), (40, 45, 60), (180, 185, 195))
        if "cerah berawan" in t:
            return ((12, 25, 50), (25, 50, 85), (200, 180, 100))
        if "berawan" in t:
            return ((15, 22, 40), (28, 40, 65), (150, 160, 180))
        return ((5, 12, 30), (18, 28, 50), (180, 200, 230))
    else:
        # Day themes
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
    """Draw smooth vertical gradient."""
    for y in range(height):
        r = int(c1[0] + (c2[0] - c1[0]) * (y / height))
        g = int(c1[1] + (c2[1] - c1[1]) * (y / height))
        b = int(c1[2] + (c2[2] - c1[2]) * (y / height))
        draw.line([(0, y), (width, y)], fill=(r, g, b))

def draw_glass(draw, bounds, fill=(255, 255, 255, 24), outline=(255, 255, 255, 48), radius=16):
    """Draw frosted glass effect box."""
    draw.rounded_rectangle(bounds, radius=radius, fill=fill, outline=outline, width=1)

def is_night_time(hour: int) -> bool:
    """Determine if current time is night (18:00-06:00)."""
    return hour >= 18 or hour < 6

def generate_weather_card(data: dict, adm4_code: str, now: datetime = None) -> io.BytesIO:
    """Generate a beautiful portrait weather card (1080x1350px) optimized for mobile."""
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

    local_time = current_dt.astimezone(tz)
    is_night = is_night_time(local_time.hour)
    c1, c2, accent = condition_theme(desc, is_night)

    # Portrait dimensions optimized for mobile
    WIDTH = 1080
    HEIGHT = 1350
    
    # Create base with gradient background
    base = Image.new("RGBA", (WIDTH, HEIGHT))
    draw_bg = ImageDraw.Draw(base)
    draw_gradient(draw_bg, WIDTH, HEIGHT, c1, c2)

    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)

    # Ambient glow effects for depth
    d.ellipse([WIDTH - 400, -150, WIDTH + 300, 500], fill=(255, 255, 255, 15))
    d.ellipse([-200, HEIGHT - 400, 500, HEIGHT + 300], fill=(255, 255, 255, 10))

    # Font definitions
    f_badge = get_font(18, bold=True)
    f_loc_main = get_font(48, bold=True)
    f_loc_sub = get_font(24, bold=False)
    f_temp_big = get_font(120, bold=True)
    f_temp_deg = get_font(64, bold=True)
    f_desc = get_font(32, bold=True)
    f_metric_lbl = get_font(18, bold=False)
    f_metric_val = get_font(28, bold=True)
    f_metric_sub = get_font(16, bold=False)
    f_period_time = get_font(18, bold=True)
    f_period_desc = get_font(14, bold=False)
    f_period_temp = get_font(24, bold=True)
    f_footer = get_font(16, bold=False)
    f_summary = get_font(16, bold=False)

    # Header with badge
    draw_glass(d, (30, 30, 280, 75), fill=(255, 255, 255, 32), outline=(255, 255, 255, 60), radius=24)
    d.text((55, 50), "🌤 BMKG", font=f_badge, fill=(255, 255, 255, 255), anchor="lm")

    # Current time
    time_str = local_time.strftime("%H:%M")
    time_label = "Malam" if is_night else "Siang"
    d.text((WIDTH - 40, 50), f"{time_str} {time_label}", font=f_metric_lbl, fill=(240, 245, 255, 220), anchor="rm")

    # Location
    loc_title = f"{location.get('desa', '')}, {location.get('kecamatan', '')}"
    loc_subtitle = f"{location.get('kotkab', '')}, {location.get('provinsi', '')}"
    d.text((40, 110), loc_title, font=f_loc_main, fill=(255, 255, 255, 255))
    d.text((42, 175), loc_subtitle, font=f_loc_sub, fill=(210, 225, 245, 200))

    # Hero weather section
    draw_glass(d, (30, 220, WIDTH - 30, 450), fill=(255, 255, 255, 20), outline=(255, 255, 255, 50), radius=28)
    
    # Large weather icon
    hero_art = render_weather_art(desc, size=140)
    overlay.alpha_composite(hero_art, (75, 245))
    
    # Temperature display
    temp_str = str(int(temp) if isinstance(temp, (int, float)) else temp)
    d.text((280, 270), temp_str, font=f_temp_big, fill=(255, 255, 255, 255))
    d.text((280 + len(temp_str) * 65, 280), "°C", font=f_temp_deg, fill=(255, 255, 255, 220))
    
    # Weather description
    d.text((280, 395), desc, font=f_desc, fill=accent)

    # Metrics row (humidity, wind, update time)
    metrics = [
        ("💧", f"{humidity}%", "Kelembapan"),
        ("💨", f"{wind_spd} km/j", f"{wind_dir}"),
        ("🕒", tz_label, "Waktu"),
    ]
    
    metric_x = 40
    metric_spacing = (WIDTH - 80) // 3
    for icon, val, label in metrics:
        box_left = metric_x + (metrics.index((icon, val, label))) * metric_spacing
        draw_glass(d, (box_left, 470, box_left + metric_spacing - 20, 560), 
                   fill=(255, 255, 255, 18), outline=(255, 255, 255, 40), radius=18)
        d.text((box_left + metric_spacing // 2 - 10, 490), icon, font=f_metric_lbl, fill=(255, 255, 255, 200))
        d.text((box_left + metric_spacing // 2 - 10, 515), val, font=f_metric_val, fill=(255, 255, 255, 255), anchor="mm")
        d.text((box_left + metric_spacing // 2 - 10, 540), label, font=f_metric_sub, fill=(180, 200, 230, 180), anchor="mm")

    # Forecast section header
    d.text((40, 590), "Prakiraan Berikutnya", font=f_loc_sub, fill=(255, 255, 255, 240))

    # Timeline cards (horizontal scroll simulation - 4 cards)
    timeline_items = future[1:5] if len(future) > 1 else future[:1]
    card_width = (WIDTH - 80) // 4
    card_height = 150
    
    for idx, (f_dt, f_row) in enumerate(timeline_items):
        card_x = 40 + idx * (card_width + 10)
        card_y = 630
        
        draw_glass(d, (card_x, card_y, card_x + card_width - 5, card_y + card_height), 
                   fill=(255, 255, 255, 24), outline=(255, 255, 255, 45), radius=16)
        
        f_time = f_dt.astimezone(tz).strftime("%H:%M")
        f_desc_short = f_row.get("weather_desc", "Cerah")[:10]
        f_temp = f_row.get("t", "--")
        
        d.text((card_x + card_width // 2 - 2, card_y + 10), f_time, 
               font=f_period_time, fill=(220, 235, 255, 230), anchor="mm")
        
        # Mini icon
        mini_art = render_weather_art(f_desc_short, size=50)
        overlay.alpha_composite(mini_art, (card_x + card_width // 2 - 25, card_y + 35))
        
        d.text((card_x + card_width // 2 - 2, card_y + 95), f_desc_short, 
               font=f_period_desc, fill=(255, 255, 255, 210), anchor="mm")
        d.text((card_x + card_width // 2 - 2, card_y + 120), f"{f_temp}°C", 
               font=f_period_temp, fill=(255, 255, 255, 255), anchor="mm")

    # Daily summary section
    d.text((40, 810), "Ringkasan Harian", font=f_loc_sub, fill=(255, 255, 255, 240))
    
    # Group forecasts by day
    from datetime import timedelta
    days = {}
    for f_dt, f_row in future:
        day = f_dt.astimezone(tz).date()
        days.setdefault(day, []).append((f_dt, f_row))
    
    summary_y = 860
    for day_idx, (day, periods) in enumerate(list(days.items())[:3]):
        if day_idx >= 3:
            break
        
        temps = [p[1].get("t") for p in periods if isinstance(p[1].get("t"), (int, float))]
        temp_range = f"{min(temps):.0f}–{max(temps):.0f}°C" if temps else "N/A"
        
        conditions = list(dict.fromkeys(p[1].get("weather_desc", "Cerah") for p in periods))
        condition_text = ", ".join(conditions[:2])
        
        day_label = "Hari ini" if day == now.astimezone(tz).date() else f"{day.strftime('%a, %d %b')}"
        
        draw_glass(d, (30, summary_y, WIDTH - 30, summary_y + 90), 
                   fill=(255, 255, 255, 15), outline=(255, 255, 255, 35), radius=14)
        
        d.text((50, summary_y + 15), day_label, font=f_metric_val, fill=(255, 255, 255, 255))
        d.text((50, summary_y + 50), temp_range, font=f_metric_lbl, fill=(255, 255, 255, 220))
        d.text((50, summary_y + 70), condition_text, font=f_summary, fill=(200, 220, 245, 200))
        
        summary_y += 100

    # Footer
    footer_y = HEIGHT - 60
    d.text((40, footer_y), "Sumber: BMKG • Lokasi: wilayah.id & OpenStreetMap", 
           font=f_footer, fill=(255, 255, 255, 150))
    d.text((WIDTH - 40, footer_y), "🍯 Honey Bot", 
           font=f_footer, fill=(255, 255, 255, 150), anchor="ra")

    # Compose and save
    final_image = Image.alpha_composite(base, overlay).convert("RGB")
    buf = io.BytesIO()
    final_image.save(buf, format="JPEG", quality=92)
    buf.seek(0)
    return buf
