"""One-shot BMKG forecasts. No user locations or responses are cached."""

import asyncio
import html
import math
import re
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx

UTC = timezone.utc
BMKG_URL = "https://api.bmkg.go.id/publik/prakiraan-cuaca"
WILAYAH_URL = "https://wilayah.id/api"
MAPPING_ERROR = (
    "Lokasi belum dapat dicocokkan secara pasti ke kelurahan/desa BMKG. "
    "Kirim /cuaca lagi dengan titik lokasi yang lebih jelas."
)


class WeatherError(Exception):
    """Safe, user-facing failure (never contains request URLs or coordinates)."""


def normalized_name(value):
    value = str(value).casefold().strip()
    aliases = {
        "daerah khusus ibukota jakarta": "dki jakarta",
        "daerah khusus jakarta": "dki jakarta",
        "daerah istimewa yogyakarta": "di yogyakarta",
    }
    value = aliases.get(value, value)
    value = re.sub(r"^(?:kota\s+(?:administrasi|adm\.?)\s+|kabupaten\s+|kota\s+|kecamatan\s+|kelurahan\s+|desa\s+)", "", value)
    return " ".join(value.split())


def match_region(rows, name, pattern):
    matches = [row for row in rows if row.get("name", "").casefold() == name.casefold()]
    if not matches:
        matches = [row for row in rows if normalized_name(row.get("name", "")) == normalized_name(name)]
    if len(matches) != 1 or not re.fullmatch(pattern, str(matches[0].get("code", ""))):
        raise WeatherError(MAPPING_ERROR)
    return matches[0]


def distance_km(lat, lon, other_lat, other_lon):
    a, b = math.radians(lat), math.radians(other_lat)
    d = math.sin((b - a) / 2) ** 2 + math.cos(a) * math.cos(b) * math.sin(math.radians(other_lon - lon) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(min(1, max(0, d))))


class WeatherService:
    def __init__(self, geocoder_url):
        self.geocoder_url = geocoder_url.rstrip("/")
        self._lock = asyncio.Lock()
        self._last_request = 0.0

    async def forecast(self, latitude, longitude):
        # Serialize requests for this private bot; also stay below Nominatim's 1/s limit.
        async with self._lock:
            await asyncio.sleep(max(0, 1.1 - (time.monotonic() - self._last_request)))
            self._last_request = time.monotonic()
            try:
                return await asyncio.wait_for(self._forecast(latitude, longitude), timeout=60)
            except WeatherError:
                raise
            except (httpx.HTTPError, asyncio.TimeoutError):
                raise WeatherError("Layanan pemetaan atau BMKG sedang tidak tersedia. Coba /cuaca lagi nanti.") from None
            except (ValueError, KeyError, TypeError, IndexError, AttributeError):
                raise WeatherError("Data wilayah atau prakiraan tidak lengkap/valid. Coba /cuaca lagi nanti.") from None

    async def _forecast(self, latitude, longitude):
        if not (math.isfinite(latitude) and math.isfinite(longitude) and -11.5 <= latitude <= 6.5 and 94 <= longitude <= 142):
            raise WeatherError("Fitur cuaca hanya tersedia untuk lokasi di Indonesia.")
        async with httpx.AsyncClient(timeout=12, headers={
            "User-Agent": "HoneyTelegramWeather/1.0 (personal on-demand BMKG forecast)",
        }) as client:
            async def get(url, **params):
                response = await client.get(url, params=params)
                response.raise_for_status()
                return response.json()

            result = await get(self.geocoder_url + "/reverse", lat=latitude, lon=longitude,
                               format="geocodejson", addressdetails=1, zoom=18,
                               layer="address", **{"accept-language": "id"})
            feature = result["features"][0]
            address = feature["properties"]["geocoding"]
            if address.get("country_code") != "id":
                raise WeatherError("Fitur cuaca hanya tersedia untuk lokasi di Indonesia.")
            point = feature["geometry"]["coordinates"]
            if feature["geometry"]["type"] != "Point" or distance_km(latitude, longitude, float(point[1]), float(point[0])) > 2:
                raise WeatherError(MAPPING_ERROR)
            admin = address.get("admin", {})
            # Indonesian OSM levels: province=4, regency=5, district=6, village=7.
            # Missing levels must fail closed; no fuzzy matching or nearest-village guess.
            code = ""
            names = []
            for level, endpoint in [(4, "provinces"), (5, "regencies"), (6, "districts"), (7, "villages")]:
                name = admin.get(f"level{level}")
                if not name:
                    raise WeatherError(MAPPING_ERROR)
                suffix = f"/{code}" if code else ""
                rows = (await get(f"{WILAYAH_URL}/{endpoint}{suffix}.json"))["data"]
                pattern = {4: r"\d{2}", 5: re.escape(code) + r"\.\d{2}",
                           6: re.escape(code) + r"\.\d{2}", 7: re.escape(code) + r"\.\d{4}"}[level]
                region = match_region(rows, name, pattern)
                code = region["code"]
                names.append(region["name"])
            data = await get(BMKG_URL, adm4=code)
            location = data["lokasi"]
            if location.get("adm4") != code or any(
                normalized_name(location.get(key, "")) != normalized_name(name)
                for key, name in zip(("provinsi", "kotkab", "kecamatan", "desa"), names)
            ):
                raise WeatherError(MAPPING_ERROR)
            return format_forecast(data, code)


def utc_date(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def measurement(value, unit):
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        return "tidak tersedia"
    return f"{value:g}{unit}"


def format_forecast(data, code, now=None):
    now = now or datetime.now(UTC)
    location = data["lokasi"]
    tz_name = location["timezone"]
    labels = {"Asia/Jakarta": "WIB", "Asia/Makassar": "WITA", "Asia/Jayapura": "WIT"}
    if tz_name not in labels:
        raise WeatherError("Zona waktu prakiraan BMKG tidak valid.")
    tz = ZoneInfo(tz_name)
    entries = [entry for entry in data["data"] if entry["lokasi"].get("adm4") == code]
    if len(entries) != 1:
        raise WeatherError(MAPPING_ERROR)
    rows = sorted((row for day in entries[0]["cuaca"] for row in day), key=lambda row: utc_date(row["utc_datetime"]))
    future = [row for row in rows if utc_date(row["utc_datetime"]) >= now]
    if not future:
        raise WeatherError("BMKG belum menyediakan prakiraan mendatang untuk wilayah ini. Coba lagi nanti.")
    productions = [utc_date(row["analysis_date"]) for row in future]
    if any(not timedelta(minutes=-15) <= now - produced <= timedelta(hours=36) for produced in productions):
        raise WeatherError("Data BMKG belum cukup mutakhir. Prakiraan lama tidak ditampilkan; coba lagi nanti.")
    escape = lambda value: html.escape(str(value))
    stamp = lambda value: utc_date(value).astimezone(tz).strftime("%d/%m %H:%M")
    first = future[0]
    place = ", ".join(escape(location[key]) for key in ("desa", "kecamatan", "kotkab", "provinsi"))
    lines = ["<b>Prakiraan Cuaca BMKG</b>", place, f"Waktu: {labels[tz_name]}", "",
             f"<b>Prakiraan terdekat — {stamp(first['utc_datetime'])}</b>",
             escape(first["weather_desc"]), f"Suhu: {measurement(first.get('t'), ' °C')}",
             f"Kelembapan: {measurement(first.get('hu'), '%')}",
             f"Angin: {measurement(first.get('ws'), ' km/jam')} dari {escape(first.get('wd') or 'tidak tersedia')}",
             "", "<b>Periode berikutnya</b>"]
    for row in future[1:8]:
        lines.append(f"{stamp(row['utc_datetime'])}: {escape(row['weather_desc'])}, {measurement(row.get('t'), ' °C')}")
    if len(future) == 1:
        lines.append("Belum tersedia.")
    days = {}
    for row in future:
        day = utc_date(row["utc_datetime"]).astimezone(tz).strftime("%d/%m")
        days.setdefault(day, []).append(row)
    lines.extend(["", "<b>Ringkasan periode yang masih tersedia</b>"])
    for day, periods in list(days.items())[:3]:
        temperatures = [row["t"] for row in periods if isinstance(row.get("t"), (int, float)) and math.isfinite(row["t"])]
        conditions = list(dict.fromkeys(row["weather_desc"] for row in periods))
        temps = f"{min(temperatures):g}–{max(temperatures):g} °C" if temperatures else "suhu tidak tersedia"
        lines.append(f"{day}: {escape(', '.join(conditions))}; {temps}")
    lines.extend(["", f"Produksi data: {min(productions).astimezone(tz):%d/%m/%Y %H:%M} {labels[tz_name]}",
                  'Sumber: <a href="https://data.bmkg.go.id/prakiraan-cuaca/">BMKG</a>',
                  f'<a href="https://www.bmkg.go.id/cuaca/prakiraan-cuaca/{code}">Prakiraan lengkap hingga 3 hari</a>',
                  'Pemetaan: © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>; kode: <a href="https://wilayah.id">Wilayah.id</a>.',
                  "", "Prakiraan wilayah, bukan pengamatan real-time di titik GPS. Periksa nama wilayah di atas; pemetaan dapat meleset dekat batas wilayah.",
                  "Untuk permintaan berikutnya, kirim /cuaca dan lokasi baru."])
    return "\n".join(lines)
