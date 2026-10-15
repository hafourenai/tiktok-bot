"""Tests for weather card generation."""

import asyncio
import io
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.environ["TELEGRAM_BOT_TOKEN"] = "test-token"
os.environ["ALLOWED_TELEGRAM_USER_ID"] = "123"
sys.path.insert(0, str(Path(__file__).parents[1]))

from weather_card import generate_weather_card, is_night_time, condition_theme
from weather_card import _forecast_rows, fit_text, get_font
from PIL import Image, ImageDraw


def get_mock_forecast(weather_desc="Cerah", hour_offset=0):
    """Generate mock forecast data."""
    NOW = datetime(2026, 10, 14, 12, tzinfo=timezone.utc) + timedelta(hours=hour_offset)
    CODE = "31.71.03.1001"
    
    location = {
        "adm4": CODE,
        "provinsi": "DKI Jakarta",
        "kotkab": "Kota Adm. Jakarta Pusat",
        "kecamatan": "Kemayoran",
        "desa": "Kemayoran",
        "timezone": "Asia/Jakarta"
    }
    
    rows = [
        {
            "utc_datetime": (NOW + timedelta(hours=i)).strftime("%Y-%m-%d %H:%M:%S"),
            "analysis_date": "2026-10-14T00:00:00",
            "weather_desc": weather_desc,
            "t": 25 + i,
            "hu": 80 - i * 2,
            "ws": 5 + i,
            "wd": "NE"
        }
        for i in range(-1, 8)
    ]
    
    return {
        "lokasi": location,
        "data": [{"lokasi": location.copy(), "cuaca": [rows]}]
    }


def test_card_generation_day():
    """Test card generation during daytime."""
    forecast = get_mock_forecast("Cerah", hour_offset=2)
    NOW = datetime(2026, 10, 14, 14, tzinfo=timezone.utc)  # 21:00 WIB (day equivalent)
    
    card = generate_weather_card(forecast, "31.71.03.1001", NOW)
    assert isinstance(card, io.BytesIO)
    assert card.tell() == 0
    assert len(card.getvalue()) > 1000  # Should be a valid JPEG


def test_card_generation_night():
    """Test card generation during nighttime."""
    forecast = get_mock_forecast("Hujan", hour_offset=-6)
    NOW = datetime(2026, 10, 14, 2, tzinfo=timezone.utc)  # 09:00 WIB (night equivalent)
    
    card = generate_weather_card(forecast, "31.71.03.1001", NOW)
    assert isinstance(card, io.BytesIO)
    assert card.tell() == 0
    assert len(card.getvalue()) > 1000


def test_card_with_different_weather():
    """Test card generation with various weather conditions."""
    conditions = ["Cerah", "Berawan", "Hujan", "Petir", "Kabut"]
    
    for condition in conditions:
        forecast = get_mock_forecast(condition)
        card = generate_weather_card(forecast, "31.71.03.1001")
        assert isinstance(card, io.BytesIO)
        assert len(card.getvalue()) > 1000


def test_card_with_missing_data():
    """Test card generation with incomplete data."""
    forecast = get_mock_forecast("Cerah")
    forecast["data"][0]["cuaca"][0][0]["t"] = None
    forecast["data"][0]["cuaca"][0][0]["hu"] = None
    
    card = generate_weather_card(forecast, "31.71.03.1001")
    assert isinstance(card, io.BytesIO)


def test_is_night_time():
    """Test night time detection."""
    assert is_night_time(20) is True
    assert is_night_time(23) is True
    assert is_night_time(0) is True
    assert is_night_time(3) is True
    assert is_night_time(5) is True
    assert is_night_time(6) is False
    assert is_night_time(12) is False
    assert is_night_time(17) is False
    assert is_night_time(18) is True


def test_condition_theme_day():
    """Test theme selection for daytime."""
    theme = condition_theme("Cerah", is_night=False)
    assert len(theme) == 3
    assert all(isinstance(t, tuple) and len(t) == 3 for t in theme)
    
    # Day cerah should have bright blue tones
    assert theme[0][0] < 50  # Red component should be low (dark)
    assert theme[1][1] > 50  # Green component should be high (bright)


def test_condition_theme_night():
    """Test theme selection for nighttime."""
    theme = condition_theme("Cerah", is_night=True)
    assert len(theme) == 3
    
    # Night theme should have darker colors
    assert sum(theme[0]) < 100  # Should be dark overall


def test_card_error_no_data():
    """Test error handling when forecast data is missing."""
    forecast = get_mock_forecast()
    forecast["data"] = []
    
    try:
        generate_weather_card(forecast, "99.99.99.9999")
        assert False, "Should raise ValueError"
    except ValueError as e:
        assert "tidak ditemukan" in str(e)


def test_card_jpeg_quality():
    """Test that generated card is valid JPEG."""
    forecast = get_mock_forecast()
    card = generate_weather_card(forecast, "31.71.03.1001")
    
    # JPEG magic bytes
    data = card.getvalue()
    assert data[:2] == b'\xff\xd8'  # JPEG start
    assert data[-2:] == b'\xff\xd9'  # JPEG end


def test_long_labels_fit_available_width():
    draw = ImageDraw.Draw(Image.new("RGB", (1080, 1350)))
    font = get_font(57, True)
    label = fit_text(draw, "Kelurahan Dengan Nama Yang Sangat Panjang Sekali", font, 950)
    assert draw.textlength(label, font=font) <= 950


def test_timestamps_preserve_timezone_offsets():
    forecast = get_mock_forecast()
    forecast["data"][0]["cuaca"] = [[{
        "utc_datetime": "2026-10-14T12:00:00+07:00", "weather_desc": "Cerah", "t": 29,
    }]]
    rows = _forecast_rows(forecast, "31.71.03.1001")
    assert rows[0][0] == datetime(2026, 10, 14, 5, tzinfo=timezone.utc)


def test_long_location_and_missing_metrics_still_render():
    forecast = get_mock_forecast()
    forecast["lokasi"]["desa"] = "Kelurahan Dengan Nama Yang Sangat Panjang Sekali"
    forecast["data"][0]["cuaca"][0][1].update(hu=None, ws=None, wd=None, weather_desc="Hujan Ringan Sampai Sedang")
    card = generate_weather_card(forecast, "31.71.03.1001", datetime(2026, 10, 14, 12, tzinfo=timezone.utc))
    assert Image.open(card).size == (1080, 1350)


if __name__ == "__main__":
    test_card_generation_day()
    test_card_generation_night()
    test_card_with_different_weather()
    test_card_with_missing_data()
    test_is_night_time()
    test_condition_theme_day()
    test_condition_theme_night()
    test_card_error_no_data()
    test_card_jpeg_quality()
    print("[SUCCESS] All weather card tests passed!")
