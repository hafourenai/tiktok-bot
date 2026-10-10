import asyncio
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from telegram.error import BadRequest

os.environ["TELEGRAM_BOT_TOKEN"] = "test-token"
os.environ["ALLOWED_TELEGRAM_USER_ID"] = "123"
sys.path.insert(0, str(Path(__file__).parents[1]))

import bot
import weather

NOW = datetime(2026, 10, 10, 4, tzinfo=timezone.utc)
CODE = "31.71.03.1001"


def forecast_data():
    location = {"adm4": CODE, "provinsi": "DKI Jakarta", "kotkab": "Kota Adm. Jakarta Pusat",
                "kecamatan": "Kemayoran", "desa": "Kemayoran", "timezone": "Asia/Jakarta"}
    rows = [{"utc_datetime": (NOW + timedelta(hours=i)).strftime("%Y-%m-%d %H:%M:%S"),
             "analysis_date": "2026-10-10T00:00:00", "weather_desc": "Cerah", "t": 30,
             "hu": 70, "ws": 5, "wd": "N"} for i in (-3, 1, 4, 7)]
    return {"lokasi": location, "data": [{"lokasi": location.copy(), "cuaca": [rows]}]}


@pytest.mark.parametrize("tz,label,expected", [("Asia/Jakarta", "WIB", "12:00"),
                                              ("Asia/Makassar", "WITA", "13:00"),
                                              ("Asia/Jayapura", "WIT", "14:00")])
def test_forecast_uses_future_slots_and_local_timezone(tz, label, expected):
    data = forecast_data()
    data["lokasi"]["timezone"] = tz
    data["lokasi"]["desa"] = "Desa <A>"
    data["data"][0]["cuaca"][0][1]["t"] = None
    data["data"][0]["cuaca"][0][0]["weather_desc"] = "PERIODE LAMA"
    text = weather.format_forecast(data, CODE, NOW)
    assert f"10/10 {expected}" in text
    assert label in text
    assert "Desa &lt;A&gt;" in text
    assert "Suhu: tidak tersedia" in text
    assert "BMKG" in text and "OpenStreetMap" in text
    assert len(text) < 4096
    assert "PERIODE LAMA" not in text


def test_old_or_mismatched_forecasts_are_rejected():
    data = forecast_data()
    with pytest.raises(weather.WeatherError, match="mendatang"):
        weather.format_forecast(data, CODE, NOW + timedelta(days=4))
    for row in data["data"][0]["cuaca"][0]:
        row["analysis_date"] = "2026-10-07T00:00:00"
    with pytest.raises(weather.WeatherError, match="mutakhir"):
        weather.format_forecast(data, CODE, NOW)
    with pytest.raises(weather.WeatherError, match="dicocokkan"):
        weather.format_forecast(data, "99.99.99.9999", NOW)


def test_ambiguous_regency_does_not_guess():
    rows = [{"name": "Kota Bandung", "code": "32.73"}, {"name": "Kabupaten Bandung", "code": "32.04"}]
    with pytest.raises(weather.WeatherError):
        weather.match_region(rows, "Bandung", r"32\.\d{2}")
    assert weather.match_region(rows, "Kota Bandung", r"32\.\d{2}")["code"] == "32.73"


def install_api(monkeypatch, country="id", missing_level=False, mismatch=False, fail=False):
    calls = []
    admin = {"level4": "Daerah Khusus Ibukota Jakarta", "level5": "Jakarta Pusat",
             "level6": "Kemayoran", "level7": "Kemayoran"}
    if missing_level:
        del admin["level7"]
    data = forecast_data()
    if mismatch:
        data["lokasi"]["desa"] = "Desa Lain"
    routes = {
        "/reverse": {"features": [{"properties": {"geocoding": {"country_code": country, "admin": admin}},
                                    "geometry": {"type": "Point", "coordinates": [106.84538, -6.16472]}}]},
        "/api/provinces.json": {"data": [{"code": "31", "name": "DKI Jakarta"}]},
        "/api/regencies/31.json": {"data": [{"code": "31.71", "name": "Kota Administrasi Jakarta Pusat"}]},
        "/api/districts/31.71.json": {"data": [{"code": "31.71.03", "name": "Kemayoran"}]},
        "/api/villages/31.71.03.json": {"data": [{"code": CODE, "name": "Kemayoran"}]},
        "/publik/prakiraan-cuaca": data,
    }

    def respond(request):
        calls.append(request)
        if fail:
            raise httpx.ReadTimeout("private coordinates in URL", request=request)
        return httpx.Response(200, json=routes[request.url.path])

    original_client = httpx.AsyncClient
    monkeypatch.setattr(weather.httpx, "AsyncClient", lambda **kwargs: original_client(transport=httpx.MockTransport(respond), **kwargs))
    original_format = weather.format_forecast
    monkeypatch.setattr(weather, "format_forecast", lambda data, code: original_format(data, code, NOW))
    return calls


def test_full_mapping_and_bmkg_request(monkeypatch):
    calls = install_api(monkeypatch)
    service = weather.WeatherService("https://geo.example")
    text = asyncio.run(service.forecast(-6.16472, 106.84538))
    assert "Kemayoran" in text
    assert len(calls) == 6
    assert dict(calls[-1].url.params) == {"adm4": CODE}
    assert not any(key in vars(service) for key in ("latitude", "longitude", "location", "cache"))


@pytest.mark.parametrize("options,expected", [({"country": "sg"}, "Indonesia"),
                                             ({"missing_level": True}, "dicocokkan"),
                                             ({"mismatch": True}, "dicocokkan"),
                                             ({"fail": True}, "tidak tersedia")])
def test_api_failures_are_safe(monkeypatch, options, expected):
    install_api(monkeypatch, **options)
    with pytest.raises(weather.WeatherError, match=expected) as error:
        asyncio.run(weather.WeatherService("https://geo.example").forecast(-6.16472, 106.84538))
    assert "106.84538" not in str(error.value)
    assert "private coordinates" not in str(error.value)


def telegram_context(user_id=123, chat_type="private"):
    status = SimpleNamespace(edit_text=AsyncMock(side_effect=BadRequest("Message can't be edited")), delete=AsyncMock())
    message = SimpleNamespace(reply_text=AsyncMock(return_value=status), date=datetime.now(timezone.utc),
                              location=SimpleNamespace(latitude=-6.16472, longitude=106.84538, live_period=None))
    update = SimpleNamespace(effective_user=SimpleNamespace(id=user_id), effective_chat=SimpleNamespace(type=chat_type),
                             effective_message=message, message=message, callback_query=None)
    service = SimpleNamespace(forecast=AsyncMock(return_value="Prakiraan BMKG"))
    context = SimpleNamespace(user_data={}, application=SimpleNamespace(bot_data={"weather_service": service}))
    return update, context, service, status


def test_each_request_requires_new_location_even_after_failure():
    async def scenario():
        update, context, service, status = telegram_context()
        await bot.handle_weather_location(update, context)
        service.forecast.assert_not_awaited()
        for failure in (False, True):
            await bot.weather_command(update, context)
            keyboard = update.message.reply_text.call_args.kwargs["reply_markup"]
            assert keyboard.keyboard[0][0].request_location
            if failure:
                service.forecast.side_effect = weather.WeatherError("BMKG tidak tersedia")
            await bot.handle_weather_location(update, context)
            expected = "BMKG tidak tersedia" if failure else "Prakiraan BMKG"
            assert update.message.reply_text.call_args.args[0] == expected
            assert "weather_request" not in context.user_data
            calls = service.forecast.await_count
            await bot.handle_weather_location(update, context)
            assert service.forecast.await_count == calls
        assert context.user_data == {}
        status.edit_text.assert_not_awaited()
    asyncio.run(scenario())


@pytest.mark.parametrize("failure", [None, weather.WeatherError("BMKG <tidak tersedia>"), RuntimeError("internal")])
@pytest.mark.parametrize("delete_fails", [False, True])
def test_weather_reply_survives_uneditable_status_and_cleanup_failure(failure, delete_fails):
    async def scenario():
        update, context, service, status = telegram_context()
        await bot.weather_command(update, context)
        update.message.reply_text.reset_mock()
        service.forecast.side_effect = failure
        if delete_fails:
            status.delete.side_effect = BadRequest("Message to delete not found")
        await bot.handle_weather_location(update, context)
        assert update.message.reply_text.await_count == 2  # status, then final reply
        reply = update.message.reply_text.call_args
        expected = ("Prakiraan BMKG" if failure is None else
                    "BMKG &lt;tidak tersedia&gt;" if isinstance(failure, weather.WeatherError) else
                    "Prakiraan gagal diproses. Kirim /cuaca lagi nanti.")
        assert reply.args[0] == expected
        assert reply.kwargs["parse_mode"] == "HTML"
        assert reply.kwargs["disable_web_page_preview"] is True
        status.edit_text.assert_not_awaited()
        status.delete.assert_awaited_once()
        assert "weather_request" not in context.user_data
    asyncio.run(scenario())


def test_waiting_for_location_does_not_report_invalid_download_url():
    async def scenario():
        update, context, service, _ = telegram_context()
        await bot.weather_command(update, context)
        update.message.text = "Jakarta"
        await bot.handle_message(update, context)
        assert "Kirim lokasi saya" in update.message.reply_text.call_args.args[0]
        service.forecast.assert_not_awaited()
    asyncio.run(scenario())


@pytest.mark.parametrize("case", ["expired", "cancel", "live", "old", "edited", "other_user", "group"])
def test_invalid_location_requests_never_call_weather(case):
    async def scenario():
        update, context, service, _ = telegram_context()
        await bot.weather_command(update, context)
        if case == "expired":
            context.user_data["weather_request"] = time.time() - 301
        elif case == "cancel":
            await bot.cancel_weather(update, context)
        elif case == "live":
            update.message.location.live_period = 900
        elif case == "old":
            update.message.date -= timedelta(hours=1)
        elif case == "edited":
            update.message = None
        elif case == "other_user":
            update.effective_user.id = 456
        else:
            update.effective_chat.type = "group"
        await bot.handle_weather_location(update, context)
        service.forecast.assert_not_awaited()
    asyncio.run(scenario())
