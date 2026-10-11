"""Public errors without coordinates or provider request URLs."""


class WeatherError(Exception):
    """Weather data cannot be safely returned."""


class RegionSelectionRequired(WeatherError):
    """GPS was received but the next administrative level needs user selection."""

    def __init__(self, selected: list[dict], candidates: list[dict]):
        super().__init__("Lokasi diterima. Pilih wilayah berikut untuk melengkapi pemetaan.")
        self.selected = [dict(region) for region in selected]
        self.candidates = [dict(region) for region in candidates]
