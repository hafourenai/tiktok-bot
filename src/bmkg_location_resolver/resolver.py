"""One-shot BMKG forecasts. No user locations or responses are cached."""

import asyncio
import html
import math
import re
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx
from .models import Forecast
from .exceptions import WeatherError, RegionSelectionRequired

UTC = timezone.utc
BMKG_URL = "https://api.bmkg.go.id/publik/prakiraan-cuaca"
WILAYAH_URL = "https://wilayah.id/api"
MAPPING_ERROR = (
    "Lokasi diterima, tetapi data peta belum dapat dicocokkan secara unik ke kelurahan/desa BMKG. "
    "Nama/kode wilayah antarpenyedia bisa berbeda atau belum lengkap. "
    "Kirim /cuaca lagi untuk mencoba titik lain di wilayah Anda."
)


def normalized_name(value):
    value = " ".join(str(value).casefold().split())
    aliases = {
        "daerah khusus ibukota jakarta": "dki jakarta",
        "daerah khusus jakarta": "dki jakarta",
        "daerah istimewa yogyakarta": "di yogyakarta",
    }
    value = aliases.get(value, value)
    value = re.sub(r"^(?:kota\s+(?:administrasi|adm\.?)\s+|kabupaten\s+|kota\s+|kecamatan\s+|kelurahan\s+|desa\s+)", "", value)
    # Formatting only, not fuzzy similarity: Ballaparang == Balla Parang,
    # Kassi-Kassi == Kassi Kassi. Callers still require a unique sibling match.
    return re.sub(r"[\s\-‐‑–—]+", "", value)


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
    def __init__(self, geocoder_url: str = "https://nominatim.openstreetmap.org"):
        self.geocoder_url = geocoder_url.rstrip("/")
        self._lock = asyncio.Lock()
        self._last_request = 0.0

    async def from_coordinates(self, latitude: float, longitude: float) -> Forecast:
        """Return validated structured BMKG data, or a typed selection requirement."""
        return await self.forecast(latitude, longitude, structured=True)

    async def regions(self, level, parent_code=""):
        endpoints = {1: "provinces", 2: "regencies", 3: "districts", 4: "villages"}
        if level not in endpoints or (level > 1 and not re.fullmatch(
            {2: r"\d{2}", 3: r"\d{2}\.\d{2}", 4: r"\d{2}\.\d{2}\.\d{2}"}[level], parent_code
        )):
            raise WeatherError("Kode induk wilayah tidak valid. Mulai lagi dengan /cuaca_manual.")
        suffix = f"/{parent_code}" if level > 1 else ""
        try:
            async with httpx.AsyncClient(timeout=12) as client:
                response = await client.get(f"{WILAYAH_URL}/{endpoints[level]}{suffix}.json")
                response.raise_for_status()
                rows = response.json()["data"]
            if not isinstance(rows, list) or not rows:
                raise ValueError
            pattern = region_code_pattern(level, parent_code)
            if any(not isinstance(row, dict) or not isinstance(row.get("name"), str)
                   or not row["name"].strip() or not re.fullmatch(pattern, str(row.get("code", ""))) for row in rows):
                raise ValueError
            return rows
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            raise WeatherError("Daftar wilayah belum tersedia. Coba /cuaca_manual lagi nanti.") from None

    async def forecast_for_regions(self, selected):
        try:
            if len(selected) != 4:
                raise ValueError
            parent = ""
            for level, region in enumerate(selected, 1):
                if not re.fullmatch(region_code_pattern(level, parent), region["code"]):
                    raise ValueError
                parent = region["code"]
            async with self._lock:
                # BMKG public API: max 60 requests/minute/IP.
                await asyncio.sleep(max(0, 1.1 - (time.monotonic() - self._last_request)))
                self._last_request = time.monotonic()
                async with httpx.AsyncClient(timeout=12) as client:
                    response = await client.get(BMKG_URL, params={"adm4": parent})
                    response.raise_for_status()
                    data = response.json()
            validate_forecast_region(data, parent, [region["name"] for region in selected])
            return format_forecast(data, parent, mapped=False)
        except WeatherError:
            raise
        except httpx.HTTPError:
            raise WeatherError("BMKG sedang tidak tersedia. Coba /cuaca_manual lagi nanti.") from None
        except (ValueError, KeyError, TypeError, IndexError, AttributeError):
            raise WeatherError("Data wilayah atau prakiraan tidak lengkap/valid. Coba /cuaca_manual lagi nanti.") from None

    async def forecast(self, latitude, longitude, *, structured=False):
        # Serialize requests for this private bot; also stay below Nominatim's 1/s limit.
        async with self._lock:
            await asyncio.sleep(max(0, 1.1 - (time.monotonic() - self._last_request)))
            self._last_request = time.monotonic()
            try:
                return await asyncio.wait_for(self._forecast(latitude, longitude, structured=structured), timeout=60)
            except WeatherError:
                raise
            except (httpx.HTTPError, asyncio.TimeoutError):
                raise WeatherError("Layanan pemetaan atau BMKG sedang tidak tersedia. Coba /cuaca lagi nanti.") from None
            except (ValueError, KeyError, TypeError, IndexError, AttributeError):
                raise WeatherError("Data wilayah atau prakiraan tidak lengkap/valid. Coba /cuaca lagi nanti.") from None

    async def _forecast(self, latitude, longitude, *, structured=False):
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
            selected = []
            for level, endpoint in [(4, "provinces"), (5, "regencies"), (6, "districts"), (7, "villages")]:
                name = admin.get(f"level{level}")
                suffix = f"/{code}" if code else ""
                rows = (await get(f"{WILAYAH_URL}/{endpoint}{suffix}.json"))["data"]
                pattern = {4: r"\d{2}", 5: re.escape(code) + r"\.\d{2}",
                           6: re.escape(code) + r"\.\d{2}", 7: re.escape(code) + r"\.\d{4}"}[level]
                if not name:
                    raise RegionSelectionRequired(selected, rows)
                try:
                    region = match_region(rows, name, pattern)
                except WeatherError:
                    raise RegionSelectionRequired(selected, rows) from None
                code = region["code"]
                names.append(region["name"])
                selected.append(region)
            data = await get(BMKG_URL, adm4=code)
            validate_forecast_region(data, code, names)
            rendered = format_forecast(data, code)
            return Forecast(code=code, location=dict(data["lokasi"]), data=data, html=rendered) if structured else rendered


def region_code_pattern(level, parent_code=""):
    return r"\d{2}" if level == 1 else re.escape(parent_code) + (r"\.\d{4}" if level == 4 else r"\.\d{2}")


def validate_forecast_region(data, code, names):
    location = data["lokasi"]
    if location.get("adm4") != code or any(
        normalized_name(location.get(key, "")) != normalized_name(name)
        for key, name in zip(("provinsi", "kotkab", "kecamatan", "desa"), names)
    ):
        raise WeatherError("Kode/nama wilayah BMKG tidak sesuai dengan wilayah yang dipilih. Prakiraan tidak ditampilkan.")


def utc_date(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def measurement(value, unit):
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        return "tidak tersedia"
    return f"{value:g}{unit}"


def condition_icon(description):
    text = str(description).casefold()
    if "petir" in text:
        return "⛈"
    if "hujan" in text:
        return "🌧"
    if "kabut" in text:
        return "🌫"
    if "cerah" in text and "berawan" in text:
        return "⛅"
    if "berawan" in text:
        return "☁️"
    if "cerah" in text:
        return "☀️"
    return "🌤"


def wind_direction(value):
    return {"N": "Utara", "NE": "Timur Laut", "E": "Timur", "SE": "Tenggara",
            "S": "Selatan", "SW": "Barat Daya", "W": "Barat", "NW": "Barat Laut"}.get(value, value or "tidak tersedia")


def format_forecast(data, code, now=None, mapped=True):
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
    lines = ["🌦 <b>Prakiraan Cuaca BMKG</b>", "",
             f"📍 <b>{escape(location['desa'])}, {escape(location['kecamatan'])}</b>",
             f"{escape(location['kotkab'])}, {escape(location['provinsi'])}", "",
             f"<b>Prakiraan terdekat</b> · {stamp(first['utc_datetime'])} {labels[tz_name]}",
             f"{condition_icon(first['weather_desc'])} <b>{escape(first['weather_desc'])}</b>",
             f"Suhu: {measurement(first.get('t'), ' °C')}",
             f"Kelembapan: {measurement(first.get('hu'), '%')}",
             f"Angin: {measurement(first.get('ws'), ' km/jam')} dari {escape(wind_direction(first.get('wd')))}",
             "", f"<b>Prakiraan berikutnya</b> · {labels[tz_name]}"]
    for row in future[1:8]:
        lines.append(f"{stamp(row['utc_datetime'])} · {condition_icon(row['weather_desc'])} {escape(row['weather_desc'])} · {measurement(row.get('t'), ' °C')}")
    if len(future) == 1:
        lines.append("Belum tersedia.")
    days = {}
    for row in future:
        day = utc_date(row["utc_datetime"]).astimezone(tz).date()
        days.setdefault(day, []).append(row)
    lines.extend(["", "<b>Ringkasan harian</b>", "Rentang suhu dari periode yang masih tersedia."])
    for day, periods in list(days.items())[:3]:
        temperatures = [row["t"] for row in periods if isinstance(row.get("t"), (int, float)) and math.isfinite(row["t"])]
        conditions = list(dict.fromkeys(row["weather_desc"] for row in periods))
        temps = f"{min(temperatures):g}–{max(temperatures):g} °C" if temperatures else "suhu tidak tersedia"
        label = "Hari ini" if day == now.astimezone(tz).date() else "Besok" if day == now.astimezone(tz).date() + timedelta(days=1) else day.strftime("%d/%m")
        lines.append(f"<b>{label} · {temps}</b>\n{escape(', '.join(conditions))}")
    lines.extend(["", f"Produksi data BMKG: {min(productions).astimezone(tz):%d/%m/%Y %H:%M} {labels[tz_name]}",
                  'Sumber: <a href="https://data.bmkg.go.id/prakiraan-cuaca/">BMKG</a>',
                  f'<a href="https://www.bmkg.go.id/cuaca/prakiraan-cuaca/{code}">Prakiraan lengkap hingga 3 hari</a>',
                  ('Peta: © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> · wilayah: <a href="https://wilayah.id">Wilayah.id</a>.'
                   if mapped else 'Wilayah dipilih manual · <a href="https://wilayah.id">Wilayah.id</a>.'),
                  "", ("<i>Prediksi wilayah, bukan pengamatan real-time. Periksa nama wilayah, terutama dekat perbatasan.</i>"
                         if mapped else "<i>Prediksi wilayah, bukan pengamatan real-time.</i>"),
                  ("Untuk permintaan berikutnya, kirim /cuaca dan lokasi baru." if mapped else
                   "Untuk permintaan berikutnya, kirim /cuaca_manual dan pilih wilayah lagi.")])
    return "\n".join(lines)
