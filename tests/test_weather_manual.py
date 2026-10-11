import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import bot
import weather
from test_weather import CODE, install_api, telegram_context

REGIONS = [
    {"code": "31", "name": "DKI Jakarta"},
    {"code": "31.71", "name": "Kota Administrasi Jakarta Pusat"},
    {"code": "31.71.03", "name": "Kemayoran"},
    {CODE: "code", "code": CODE, "name": "Kemayoran"},
]

# Fix REGIONS so each entry is a proper dict
REGIONS = [
    {"code": "31", "name": "DKI Jakarta"},
    {"code": "31.71", "name": "Kota Administrasi Jakarta Pusat"},
    {"code": "31.71.03", "name": "Kemayoran"},
    {"code": CODE, "name": "Kemayoran"},
]


def make_callback_query(data, message, user_id=123, chat_type="private"):
    """Build a minimal callback_query-bearing update for weather_region_callback."""
    cq = SimpleNamespace(
        data=data,
        answer=AsyncMock(),
        edit_message_text=AsyncMock(),
        message=message,
    )
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=user_id),
        effective_chat=SimpleNamespace(type=chat_type),
        effective_message=message,
        message=message,
        callback_query=cq,
    )
    return update, cq


def make_menu_message():
    """A fake bot message that supports edit_text (returned by reply_text)."""
    msg = SimpleNamespace(
        edit_text=AsyncMock(),
        reply_text=AsyncMock(),
        message_id=42,
    )
    # reply_text returns itself so state["menu_message_id"] is set
    msg.reply_text.return_value = msg
    return msg


def manual_context():
    update, context, service, status = telegram_context()
    service.regions = AsyncMock(side_effect=[[region] for region in REGIONS])
    service.forecast_for_regions = AsyncMock(return_value="Prakiraan manual BMKG")
    # Make the initial reply_text return a message with edit_text and message_id
    menu_msg = make_menu_message()
    update.message.reply_text.return_value = menu_msg
    update.effective_message.reply_text.return_value = menu_msg
    return update, context, service, status


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


@pytest.mark.parametrize("failed_forecast", [False, True])
def test_manual_conversation_via_inline_buttons(failed_forecast):
    """Selecting all 4 levels via inline callback buttons produces a forecast."""
    async def scenario():
        update, context, service, _ = manual_context()
        context.user_data["weather_request"] = 1
        await bot.weather_manual_command(update, context)
        assert "weather_request" not in context.user_data
        assert "weather_manual" in context.user_data

        if failed_forecast:
            service.forecast_for_regions.side_effect = weather.WeatherError("BMKG tidak tersedia")

        # Simulate clicking each region button in turn
        state = context.user_data["weather_manual"]
        menu_msg = make_menu_message()
        for region in REGIONS:
            cq_update, cq = make_callback_query(f"wr_sel:{region['code']}", menu_msg)
            context.user_data["weather_manual"] = state
            # Refresh side_effect correctly per level
            await bot.weather_region_callback(cq_update, context)
            state = context.user_data.get("weather_manual", state)

        service.forecast_for_regions.assert_awaited_once_with(REGIONS)
        service.forecast.assert_not_awaited()
        assert "weather_manual" not in context.user_data
        expected = "BMKG tidak tersedia" if failed_forecast else "Prakiraan manual BMKG"
        assert expected in menu_msg.edit_text.call_args.args[0]
    asyncio.run(scenario())


@pytest.mark.parametrize("case", ["cancel_button", "cancel_command", "expired", "gps_command", "denied"])
def test_manual_request_cleanup_and_access(case):
    async def scenario():
        update, context, service, _ = manual_context()
        await bot.weather_manual_command(update, context)
        assert "weather_manual" in context.user_data
        state = context.user_data["weather_manual"]
        menu_msg = make_menu_message()

        if case == "cancel_button":
            cq_update, cq = make_callback_query(bot.WEATHER_CANCEL, menu_msg)
            await bot.weather_region_callback(cq_update, context)
        elif case == "cancel_command":
            await bot.cancel_weather(update, context)
        elif case == "expired":
            state["started"] -= 301
            cq_update, cq = make_callback_query(f"wr_sel:{REGIONS[0]['code']}", menu_msg)
            await bot.weather_region_callback(cq_update, context)
        elif case == "gps_command":
            await bot.weather_command(update, context)
        elif case == "denied":
            cq_update, cq = make_callback_query(f"wr_sel:{REGIONS[0]['code']}", menu_msg, user_id=456)
            await bot.weather_region_callback(cq_update, context)
            assert "weather_manual" in context.user_data  # denied user doesn't clear state
            return

        assert "weather_manual" not in context.user_data
        service.forecast_for_regions.assert_not_awaited()
    asyncio.run(scenario())


def test_manual_button_starts_conversation():
    async def scenario():
        update, context, service, _ = manual_context()
        await bot.weather_command(update, context)
        # Simulate clicking the "Input wilayah manual" action callback
        cq = SimpleNamespace(
            data="action:cuaca_manual",
            answer=AsyncMock(),
        )
        update.callback_query = cq
        context.args = []
        await bot.action_callback(update, context)
        service.regions.assert_awaited_once_with(1)
        assert "weather_manual" in context.user_data
    asyncio.run(scenario())


def inline_button_texts(edit_text_mock):
    """Extract all button labels from the last edit_text call's InlineKeyboardMarkup."""
    call_kwargs = edit_text_mock.call_args
    if call_kwargs is None:
        return []
    markup = call_kwargs.kwargs.get("reply_markup") or (
        call_kwargs.args[1] if len(call_kwargs.args) > 1 else None
    )
    if markup is None:
        return []
    return [btn.text for row in markup.inline_keyboard for btn in row]


def test_pagination_via_inline_buttons():
    """Next/previous page buttons edit the same message and update page state."""
    async def scenario():
        update, context, service, _ = manual_context()
        depok = {"code": "32.76", "name": "Kota Depok"}
        rows = [{"code": f"32.{i:02}", "name": f"Kabupaten Contoh {i}"} for i in range(1, 24)] + [depok]
        state = {"started": time.time(), "selected": [{"code": "32", "name": "Jawa Barat"}], "rows": rows}
        context.user_data["weather_manual"] = state
        menu_msg = make_menu_message()

        await bot.prompt_weather_region(menu_msg, state)
        # Page 1: Depok should not be visible yet
        markup = menu_msg.reply_text.call_args.kwargs["reply_markup"]
        texts_p1 = [btn.text for row in markup.inline_keyboard for btn in row]
        assert "Kota Depok" not in texts_p1
        assert "Berikutnya →" in texts_p1

        # Press "Berikutnya →"
        cq_update, cq = make_callback_query(bot.WEATHER_NEXT, menu_msg)
        await bot.weather_region_callback(cq_update, context)
        texts_p2 = inline_button_texts(menu_msg.edit_text)
        assert "Kota Depok" in texts_p2
        assert "← Sebelumnya" in texts_p2
        assert state["page"] == 1

        # Press "← Sebelumnya"
        cq_update, cq = make_callback_query(bot.WEATHER_PREVIOUS, menu_msg)
        await bot.weather_region_callback(cq_update, context)
        assert state["page"] == 0
    asyncio.run(scenario())


def test_inline_cancel_button_ends_session():
    async def scenario():
        update, context, service, _ = manual_context()
        await bot.weather_manual_command(update, context)
        menu_msg = make_menu_message()
        cq_update, cq = make_callback_query(bot.WEATHER_CANCEL, menu_msg)
        await bot.weather_region_callback(cq_update, context)
        assert "weather_manual" not in context.user_data
        cq.edit_message_text.assert_awaited_once()
        assert "dibatalkan" in cq.edit_message_text.call_args.args[0]
    asyncio.run(scenario())


def test_expired_session_via_inline_button():
    async def scenario():
        update, context, service, _ = manual_context()
        await bot.weather_manual_command(update, context)
        context.user_data["weather_manual"]["started"] -= 301
        menu_msg = make_menu_message()
        cq_update, cq = make_callback_query(f"wr_sel:{REGIONS[0]['code']}", menu_msg)
        await bot.weather_region_callback(cq_update, context)
        assert "weather_manual" not in context.user_data
        cq.edit_message_text.assert_awaited_once()
        assert "kedaluwarsa" in cq.edit_message_text.call_args.args[0]
    asyncio.run(scenario())
