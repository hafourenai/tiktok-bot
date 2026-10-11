import asyncio
from types import SimpleNamespace

import pytest

from bmkg_location_resolver import BMKGWeatherResolver, RegionSelectionRequired, WeatherError, Forecast
from bmkg_location_resolver.telegram import coordinates_from_message
from test_weather import install_api, telegram_context
import bot


def test_package_returns_structured_validated_forecast(monkeypatch):
    install_api(monkeypatch)
    result = asyncio.run(BMKGWeatherResolver().from_coordinates(-6.16472, 106.84538))
    assert isinstance(result, Forecast)
    assert result.code == "31.71.03.1001"
    assert result.location["desa"] == "Kemayoran"
    assert "BMKG" in result.html


def test_missing_admin_returns_choices_under_resolved_parent(monkeypatch):
    calls = install_api(monkeypatch, missing_level=True)
    with pytest.raises(RegionSelectionRequired) as caught:
        asyncio.run(BMKGWeatherResolver().from_coordinates(-6.16472, 106.84538))
    assert len(caught.value.selected) == 3
    assert caught.value.candidates[0]["code"] == "31.71.03.1001"
    assert all(request.url.host != "api.bmkg.go.id" for request in calls)


def test_gps_fallback_continues_at_missing_level_without_retaining_coordinates():
    async def scenario():
        update, context, service, _ = telegram_context()
        selected = [{"code": "31", "name": "DKI Jakarta"}]
        candidates = [{"code": "31.71", "name": "Kota Administrasi Jakarta Pusat"}]
        service.forecast.side_effect = RegionSelectionRequired(selected, candidates)
        await bot.weather_command(update, context)
        await bot.handle_weather_location(update, context)
        state = context.user_data["weather_manual"]
        assert state["selected"] == selected
        assert state["rows"] == candidates
        assert "weather_request" not in context.user_data
        assert "latitude" not in state and "longitude" not in state
        assert "langkah 2/4" in update.message.reply_text.call_args.args[0]
        await bot.cancel_weather(update, context)
        assert context.user_data == {}
    asyncio.run(scenario())


def test_adapter_accepts_venue_without_telegram_dependency():
    point = SimpleNamespace(latitude=-6.1, longitude=106.8)
    result = coordinates_from_message(SimpleNamespace(venue=SimpleNamespace(location=point)))
    assert result.latitude == -6.1
    with pytest.raises(WeatherError):
        coordinates_from_message(SimpleNamespace())
