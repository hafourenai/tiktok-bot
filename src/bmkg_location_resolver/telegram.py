"""Duck-typed Telegram adapter; importing this module needs no Telegram SDK."""

from .exceptions import WeatherError
from .models import Coordinates


def coordinates_from_message(message: object) -> Coordinates:
    location = getattr(message, "location", None)
    if location is None:
        location = getattr(getattr(message, "venue", None), "location", None)
    if location is None:
        raise WeatherError("Pesan tidak memiliki koordinat. Gunakan Lampiran → Lokasi.")
    if getattr(location, "live_period", None):
        raise WeatherError("Kirim lokasi statis yang baru, bukan live location.")
    return Coordinates(latitude=location.latitude, longitude=location.longitude)
