"""Reusable Indonesian BMKG weather and location resolver."""

from .exceptions import RegionSelectionRequired, WeatherError
from .models import Coordinates, Forecast
from .resolver import WeatherService

BMKGWeatherResolver = WeatherService
__version__ = "0.1.0"
__all__ = ["BMKGWeatherResolver", "WeatherService", "WeatherError", "RegionSelectionRequired", "Coordinates", "Forecast"]
