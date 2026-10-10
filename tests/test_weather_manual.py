import asyncio
import time
from unittest.mock import AsyncMock

import pytest

import bot
import weather
from test_weather import CODE, install_api, telegram_context

REGIONS = [
    {"code": "31", "name": "DKI Jakarta"},
    {"code": "31.71", "name": "Kota Administrasi Jakarta Pusat"},
    {"code": "31.71.03", "name": "Kemayoran"},
    {"code": CODE, "name": "Kemayoran"},
]


def test_manual_service_uses_only_region_directory_and_bmkg(monkeypatch):
    calls = install_api(monkeypatch)

    async def scenario():
        service = weather.WeatherService("https://geo.example")
        parent = ""
        selected = []
        for level in range(1, 5):
            rows = await service.regions(level, parent)
            selected.append(rows[0])
            parent = rows[0]["code"]
        text = await service.forecast_for_regions(selected)
        assert "Wilayah dipilih manual" in text
        assert "OpenStreetMap" not in text
        assert all(request.url.path != "/reverse" for request in calls)
        assert dict(calls[-1].url.params) == {"adm4": CODE}
    asyncio.run(scenario())


def test_manual_service_rejects_wrong_bmkg_region(monkeypatch):
    install_api(monkeypatch, mismatch=True)
    with pytest.raises(weather.WeatherError, match="sesuai"):
        asyncio.run(weather.WeatherService("https://geo.example").forecast_for_regions(REGIONS))


def manual_context():
    update, context, service, status = telegram_context()
    service.regions = AsyncMock(side_effect=[[region] for region in REGIONS])
    service.forecast_for_regions = AsyncMock(return_value="Prakiraan manual BMKG")
    return update, context, service, status


@pytest.mark.parametrize("failed_forecast", [False, True])
def test_manual_conversation_validates_every_level_and_consumes_request(failed_forecast):
    async def scenario():
        update, context, service, _ = manual_context()
        context.user_data["weather_request"] = 1
        await bot.weather_manual_command(update, context)
        assert "weather_request" not in context.user_data
        if failed_forecast:
            service.forecast_for_regions.side_effect = weather.WeatherError("BMKG tidak tersedia")
        update.message.text = "Nama salah"
        await bot.handle_message(update, context)
        assert context.user_data["weather_manual"]["selected"] == []
        for region in REGIONS:
            update.message.text = region["name"]
            await bot.handle_message(update, context)
        assert service.regions.await_args_list[0].args == (1,)
        for call, level, region in zip(service.regions.await_args_list[1:], range(2, 5), REGIONS):
            assert call.args == (level, region["code"])
        service.forecast_for_regions.assert_awaited_once_with(REGIONS)
        service.forecast.assert_not_awaited()
        assert context.user_data == {}
        expected = "BMKG tidak tersedia" if failed_forecast else "Prakiraan manual BMKG"
        assert update.message.reply_text.call_args.args[0] == expected
        await bot.handle_message(update, context)
        assert service.forecast_for_regions.await_count == 1
    asyncio.run(scenario())


@pytest.mark.parametrize("case", ["cancel", "expired", "gps_command", "denied", "directory_error"])
def test_manual_request_cleanup_and_access(case):
    async def scenario():
        update, context, service, _ = manual_context()
        await bot.weather_manual_command(update, context)
        update.message.text = "DKI Jakarta"
        if case == "cancel":
            await bot.cancel_weather(update, context)
        elif case == "expired":
            context.user_data["weather_manual"]["started"] -= 301
            await bot.handle_message(update, context)
        elif case == "gps_command":
            await bot.weather_command(update, context)
        elif case == "denied":
            update.effective_user.id = 456
            await bot.handle_message(update, context)
            assert context.user_data["weather_manual"]["selected"] == []
            return
        else:
            service.regions.side_effect = weather.WeatherError("Daftar wilayah belum tersedia")
            await bot.handle_message(update, context)
        assert "weather_manual" not in context.user_data
        service.forecast_for_regions.assert_not_awaited()
    asyncio.run(scenario())


def test_manual_button_starts_conversation():
    async def scenario():
        update, context, service, _ = manual_context()
        await bot.weather_command(update, context)
        update.message.text = bot.WEATHER_MANUAL_LABEL
        await bot.handle_message(update, context)
        service.regions.assert_awaited_once_with(1)
        assert "provinsi" in update.message.reply_text.call_args.args[0]
        assert "weather_manual" in context.user_data
    asyncio.run(scenario())


def button_texts(message):
    return [button.text for row in message.reply_text.call_args.kwargs["reply_markup"].keyboard for button in row]


@pytest.mark.parametrize("selection", ["Depok", "Kota Depok"])
def test_depok_visible_on_next_page_and_selectable_by_name(selection):
    async def scenario():
        update, context, service, _ = manual_context()
        depok = {"code": "32.76", "name": "Kota Depok"}
        rows = [{"code": f"32.{i:02}", "name": f"Kabupaten Contoh {i}"} for i in range(1, 24)] + [depok]
        state = {"started": time.time(), "selected": [{"code": "32", "name": "Jawa Barat"}], "rows": rows}
        context.user_data["weather_manual"] = state
        await bot.prompt_weather_region(update.message, state)
        assert "Kota Depok" not in button_texts(update.message)
        assert bot.WEATHER_NEXT in button_texts(update.message)
        update.message.text = bot.WEATHER_NEXT
        await bot.handle_message(update, context)
        assert "Kota Depok" in button_texts(update.message)
        assert bot.WEATHER_PREVIOUS in button_texts(update.message)
        assert "Halaman 2/2" in update.message.reply_text.call_args.args[0]
        update.message.text = bot.WEATHER_PREVIOUS
        await bot.handle_message(update, context)
        assert state["page"] == 0
        # Direct name input can select Depok even from another page.
        service.regions.side_effect = None
        service.regions.return_value = [{"code": "32.76.01", "name": "Pancoran Mas"}]
        update.message.text = selection
        await bot.handle_message(update, context)
        service.regions.assert_awaited_once_with(3, "32.76")
        assert state["selected"][-1] == depok
        assert state["page"] == 0
        assert "search_rows" not in state
    asyncio.run(scenario())


def test_partial_and_ambiguous_search_require_explicit_selection():
    async def scenario():
        update, context, service, _ = manual_context()
        rows = [{"code": "32.04", "name": "Kabupaten Bandung"},
                {"code": "32.73", "name": "Kota Bandung"},
                {"code": "32.76", "name": "Kota Depok"}]
        state = {"started": time.time(), "selected": [{"code": "32", "name": "Jawa Barat"}], "rows": rows}
        context.user_data["weather_manual"] = state
        for query in ("Bandung", "Band"):
            update.message.text = query
            await bot.handle_message(update, context)
            assert len(state["search_rows"]) == 2
            assert "Kota Bandung" in button_texts(update.message)
            assert "Kabupaten Bandung" in button_texts(update.message)
            assert "Kota Depok" not in button_texts(update.message)
            service.regions.assert_not_awaited()
        update.message.text = "Dep"
        await bot.handle_message(update, context)
        assert state["search_rows"] == [rows[2]]
        assert len(state["selected"]) == 1  # even a unique partial search is not a confirmed selection
        update.message.text = bot.WEATHER_ALL
        await bot.handle_message(update, context)
        assert "search_rows" not in state
        assert "Kabupaten Bandung" in button_texts(update.message)
        service.regions.assert_not_awaited()
    asyncio.run(scenario())
