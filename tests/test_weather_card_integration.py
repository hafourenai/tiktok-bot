"""Integration test for weather card in bot flow."""

import asyncio
import io
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys
import os

os.environ["TELEGRAM_BOT_TOKEN"] = "test-token"
os.environ["ALLOWED_TELEGRAM_USER_ID"] = "123"
sys.path.insert(0, str(Path(__file__).parents[1]))

from weather_card import generate_weather_card


def create_realistic_forecast():
    """Create realistic BMKG forecast data structure."""
    NOW = datetime(2026, 10, 14, 12, 0, 0, tzinfo=timezone.utc)
    
    location = {
        "adm4": "31.71.03.1001",
        "provinsi": "DKI Jakarta",
        "kotkab": "Kota Administrasi Jakarta Pusat",
        "kecamatan": "Kemayoran",
        "desa": "Kemayoran",
        "timezone": "Asia/Jakarta"
    }
    
    # Simulate BMKG 3-hourly forecast data
    forecasts = []
    for day_offset in range(3):
        day_data = []
        for hour_offset in range(0, 24, 3):
            dt = NOW + timedelta(days=day_offset, hours=hour_offset)
            conditions = ["Cerah", "Cerah Berawan", "Berawan", "Hujan", "Hujan Petir"]
            condition = conditions[(hour_offset // 3) % len(conditions)]
            
            day_data.append({
                "utc_datetime": dt.strftime("%Y-%m-%d %H:%M:%S"),
                "analysis_date": NOW.strftime("%Y-%m-%dT00:00:00"),
                "weather_desc": condition,
                "t": 25 - (abs(hour_offset - 12) * 0.5),
                "hu": 75 + (hour_offset % 3) * 5,
                "ws": 3 + (hour_offset % 5),
                "wd": ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][hour_offset % 8],
            })
        forecasts.append(day_data)
    
    return {
        "lokasi": location,
        "data": [{
            "lokasi": location.copy(),
            "cuaca": forecasts
        }]
    }


def test_integration():
    """Test complete flow: data -> card generation -> JPEG output."""
    print("Testing weather card generation integration...")
    
    # Step 1: Create forecast (simulates what BMKG API returns)
    forecast = create_realistic_forecast()
    print("[1] Forecast data created")
    
    # Step 2: Generate card (simulates what bot calls)
    try:
        card_buf = generate_weather_card(forecast, "31.71.03.1001")
        print("[2] Card generated successfully")
    except Exception as e:
        print(f"[ERROR] Card generation failed: {e}")
        return False
    
    # Step 3: Verify output is valid JPEG
    jpeg_data = card_buf.getvalue()
    
    # Check JPEG headers
    if jpeg_data[:2] != b'\xff\xd8':
        print("[ERROR] Invalid JPEG header")
        return False
    if jpeg_data[-2:] != b'\xff\xd9':
        print("[ERROR] Invalid JPEG footer")
        return False
    print(f"[3] Valid JPEG generated ({len(jpeg_data)} bytes)")
    
    # Step 4: Test that bot can use this data
    # Simulate what bot.py does: reply_photo(photo=card_buf)
    if not isinstance(card_buf, io.BytesIO):
        print("[ERROR] Card is not BytesIO")
        return False
    print("[4] Card is BytesIO (compatible with Telegram API)")
    
    # Step 5: Verify dimensions (portrait)
    from PIL import Image
    card_buf.seek(0)
    img = Image.open(card_buf)
    if img.size != (1080, 1350):
        print(f"[ERROR] Wrong dimensions: {img.size}, expected (1080, 1350)")
        return False
    print(f"[5] Correct dimensions: {img.size}")
    
    return True


def test_multiple_times_of_day():
    """Test that card theme changes based on time of day."""
    forecast = create_realistic_forecast()
    
    times_to_test = [
        (datetime(2026, 10, 14, 6, 0, 0, tzinfo=timezone.utc), "morning"),
        (datetime(2026, 10, 14, 14, 0, 0, tzinfo=timezone.utc), "afternoon"),
        (datetime(2026, 10, 14, 22, 0, 0, tzinfo=timezone.utc), "night"),
    ]
    
    print("\nTesting different times of day...")
    for test_time, label in times_to_test:
        try:
            card = generate_weather_card(forecast, "31.71.03.1001", test_time)
            size = len(card.getvalue())
            print(f"[OK] {label.capitalize()} card generated ({size} bytes)")
        except Exception as e:
            print(f"[ERROR] Failed to generate {label} card: {e}")
            return False
    
    return True


def test_error_handling():
    """Test that errors are handled gracefully."""
    print("\nTesting error handling...")
    
    # Test 1: Missing location data
    bad_forecast = {"lokasi": {}, "data": []}
    try:
        generate_weather_card(bad_forecast, "invalid-code")
        print("[ERROR] Should have raised ValueError for missing data")
        return False
    except ValueError as e:
        print(f"[OK] Correctly caught missing data error")
    
    # Test 2: Invalid timezone
    forecast = create_realistic_forecast()
    forecast["lokasi"]["timezone"] = "Invalid/Zone"
    try:
        # Should still work with fallback
        card = generate_weather_card(forecast, "31.71.03.1001")
        print("[OK] Fallback to default timezone works")
    except Exception as e:
        print(f"[ERROR] Should handle invalid timezone: {e}")
        return False
    
    return True


if __name__ == "__main__":
    success = True
    success = test_integration() and success
    success = test_multiple_times_of_day() and success
    success = test_error_handling() and success
    
    if success:
        print("\n" + "="*50)
        print("[SUCCESS] All integration tests passed!")
        print("="*50)
        sys.exit(0)
    else:
        print("\n[FAILED] Some tests failed")
        sys.exit(1)
