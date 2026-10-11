"""Professional Vector Icon Renderer using Pillow pure drawing for pixel-perfect weather cards."""

import math
from PIL import Image, ImageDraw


def draw_sun(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int = 24, color=(253, 204, 21, 255)):
    # Sun disk
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
    # Sun rays
    ray_len = int(r * 0.45)
    ray_dist = int(r * 1.35)
    for angle in range(0, 360, 45):
        rad = math.radians(angle)
        x1 = cx + math.cos(rad) * ray_dist
        y1 = cy + math.sin(rad) * ray_dist
        x2 = cx + math.cos(rad) * (ray_dist + ray_len)
        y2 = cy + math.sin(rad) * (ray_dist + ray_len)
        draw.line([(x1, y1), (x2, y2)], fill=color, width=max(2, int(r * 0.12)))


def draw_cloud(draw: ImageDraw.ImageDraw, cx: int, cy: int, scale: float = 1.0, color=(235, 242, 250, 240)):
    # Cloud consists of 3-4 overlapping circles and a base pill
    w = int(50 * scale)
    h = int(24 * scale)
    base_y = cy + int(4 * scale)
    draw.rounded_rectangle([cx - w, base_y - h, cx + w, base_y + h], radius=int(h), fill=color)
    # Puffs
    draw.ellipse([cx - int(32 * scale), cy - int(24 * scale), cx + int(4 * scale), cy + int(14 * scale)], fill=color)
    draw.ellipse([cx - int(6 * scale), cy - int(32 * scale), cx + int(36 * scale), cy + int(14 * scale)], fill=color)


def draw_rain(draw: ImageDraw.ImageDraw, cx: int, cy: int, count: int = 4, color=(96, 165, 250, 230)):
    start_x = cx - (count - 1) * 7
    for i in range(count):
        rx = start_x + i * 14
        ry = cy + 12
        draw.line([(rx, ry), (rx - 5, ry + 15)], fill=color, width=3)


def draw_lightning(draw: ImageDraw.ImageDraw, cx: int, cy: int, color=(250, 204, 21, 255)):
    points = [
        (cx + 4, cy + 10),
        (cx - 6, cy + 24),
        (cx + 2, cy + 24),
        (cx - 4, cy + 38),
        (cx + 8, cy + 22),
        (cx + 1, cy + 22),
    ]
    draw.polygon(points, fill=color)


def render_weather_art(desc: str, size: int = 90) -> Image.Image:
    """Returns a transparent RGBA image containing vector-drawn weather iconography."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    text = (desc or "").casefold()
    cx, cy = size // 2, size // 2
    scale = size / 100.0

    if "petir" in text:
        draw_cloud(draw, cx, cy - int(10 * scale), scale=scale * 0.88, color=(160, 175, 195, 245))
        draw_lightning(draw, cx - int(4 * scale), cy + int(4 * scale), color=(253, 224, 71, 255))
        draw_rain(draw, cx + int(10 * scale), cy + int(10 * scale), count=2, color=(96, 165, 250, 240))
    elif "hujan" in text:
        draw_cloud(draw, cx, cy - int(12 * scale), scale=scale * 0.88, color=(180, 198, 218, 245))
        draw_rain(draw, cx, cy + int(6 * scale), count=4, color=(147, 197, 253, 245))
    elif "kabut" in text or "asap" in text:
        for offset_y in [-12, -2, 8, 18]:
            y = cy + int(offset_y * scale)
            draw.rounded_rectangle([cx - int(34 * scale), y, cx + int(34 * scale), y + int(4 * scale)], radius=2, fill=(209, 213, 219, 210))
    elif "cerah berawan" in text:
        draw_sun(draw, cx - int(14 * scale), cy - int(14 * scale), r=int(18 * scale), color=(253, 204, 21, 255))
        draw_cloud(draw, cx + int(8 * scale), cy + int(8 * scale), scale=scale * 0.72, color=(245, 248, 255, 250))
    elif "berawan" in text:
        draw_cloud(draw, cx - int(8 * scale), cy - int(8 * scale), scale=scale * 0.65, color=(190, 205, 220, 200))
        draw_cloud(draw, cx + int(4 * scale), cy + int(8 * scale), scale=scale * 0.82, color=(245, 248, 255, 250))
    elif "cerah" in text:
        draw_sun(draw, cx, cy, r=int(26 * scale), color=(253, 186, 116, 255))
    else:
        draw_sun(draw, cx - int(12 * scale), cy - int(12 * scale), r=int(18 * scale), color=(253, 204, 21, 255))
        draw_cloud(draw, cx + int(8 * scale), cy + int(8 * scale), scale=scale * 0.7, color=(245, 248, 255, 245))

    return img
