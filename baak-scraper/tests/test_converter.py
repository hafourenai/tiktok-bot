"""Tests for time converter."""

import pytest
from scraper.converter import (
    parse_waktu_slots,
    convert_slots_to_time,
    convert_waktu,
    JADWAL_KULIAH,
)


class TestParseWaktuSlots:
    """Test waktu notation parsing."""

    def test_single_slot(self):
        """Test parsing single slot."""
        slots, warnings = parse_waktu_slots("1")
        assert slots == [1]
        assert len(warnings) == 0

    def test_consecutive_slots(self):
        """Test parsing consecutive slots."""
        slots, warnings = parse_waktu_slots("1/2/3")
        assert slots == [1, 2, 3]
        assert len(warnings) == 0

    def test_two_slots(self):
        """Test parsing two consecutive slots."""
        slots, warnings = parse_waktu_slots("5/6")
        assert slots == [5, 6]
        assert len(warnings) == 0

    def test_non_consecutive_slots(self):
        """Test parsing non-consecutive slots (should warn)."""
        slots, warnings = parse_waktu_slots("1/3")
        assert slots == [1, 3]
        assert any("tidak berurutan" in w.lower() for w in warnings)

    def test_invalid_slot_high(self):
        """Test slot out of range (>14)."""
        slots, warnings = parse_waktu_slots("15")
        assert slots is None
        assert any("luar range" in w for w in warnings)

    def test_invalid_slot_low(self):
        """Test slot out of range (<1)."""
        slots, warnings = parse_waktu_slots("0")
        assert slots is None
        assert any("luar range" in w for w in warnings)

    def test_mixed_valid_invalid(self):
        """Test mix of valid and invalid slots."""
        slots, warnings = parse_waktu_slots("1/2/15")
        assert slots == [1, 2]
        assert any("luar range" in w for w in warnings)

    def test_empty_string(self):
        """Test empty input."""
        slots, warnings = parse_waktu_slots("")
        assert slots is None
        assert len(warnings) > 0

    def test_non_numeric(self):
        """Test non-numeric input."""
        slots, warnings = parse_waktu_slots("a/b/c")
        assert slots is None
        assert any("bukan angka" in w for w in warnings)

    def test_whitespace_handling(self):
        """Test whitespace in slots."""
        slots, warnings = parse_waktu_slots("1 / 2 / 3")
        assert slots == [1, 2, 3]
        assert len(warnings) == 0


class TestConvertSlotsToTime:
    """Test slot to time conversion."""

    def test_single_slot_1(self):
        """Test slot 1: 07.30-08.30."""
        jam_mulai, jam_selesai, jam_display = convert_slots_to_time([1])
        assert jam_mulai == "07:30"
        assert jam_selesai == "08:30"
        assert jam_display == "07.30–08.30 WIB"

    def test_slots_1_2(self):
        """Test slots 1-2: 07.30-09.30."""
        jam_mulai, jam_selesai, jam_display = convert_slots_to_time([1, 2])
        assert jam_mulai == "07:30"
        assert jam_selesai == "09:30"
        assert jam_display == "07.30–09.30 WIB"

    def test_slots_5_6(self):
        """Test slots 5-6: 11.30-13.30."""
        jam_mulai, jam_selesai, jam_display = convert_slots_to_time([5, 6])
        assert jam_mulai == "11:30"
        assert jam_selesai == "13:30"
        assert jam_display == "11.30–13.30 WIB"

    def test_slot_14(self):
        """Test slot 14 (last): 20.30-21.30."""
        jam_mulai, jam_selesai, jam_display = convert_slots_to_time([14])
        assert jam_mulai == "20:30"
        assert jam_selesai == "21:30"
        assert jam_display == "20.30–21.30 WIB"

    def test_all_14_slots(self):
        """Test all 14 consecutive slots."""
        jam_mulai, jam_selesai, jam_display = convert_slots_to_time(list(range(1, 15)))
        assert jam_mulai == "07:30"
        assert jam_selesai == "21:30"
        assert jam_display == "07.30–21.30 WIB"

    def test_slots_4_5(self):
        """Test slots 4-5: 10.30-12.30."""
        jam_mulai, jam_selesai, jam_display = convert_slots_to_time([4, 5])
        assert jam_mulai == "10:30"
        assert jam_selesai == "12:30"
        assert jam_display == "10.30–12.30 WIB"

    def test_empty_slots(self):
        """Test empty slot list."""
        result = convert_slots_to_time([])
        assert result == (None, None, None)


class TestConvertWaktu:
    """Test complete waktu conversion."""

    def test_valid_single(self):
        """Test valid single slot conversion."""
        jam_mulai, jam_selesai, jam_display, warnings = convert_waktu("1")
        assert jam_mulai == "07:30"
        assert jam_selesai == "08:30"
        assert jam_display == "07.30–08.30 WIB"
        assert len(warnings) == 0

    def test_valid_range(self):
        """Test valid range conversion."""
        jam_mulai, jam_selesai, jam_display, warnings = convert_waktu("1/2/3")
        assert jam_mulai == "07:30"
        assert jam_selesai == "10:30"
        assert jam_display == "07.30–10.30 WIB"
        assert len(warnings) == 0

    def test_invalid_input(self):
        """Test invalid input returns None times."""
        jam_mulai, jam_selesai, jam_display, warnings = convert_waktu("invalid")
        assert jam_mulai is None
        assert jam_selesai is None
        assert jam_display is None
        assert len(warnings) > 0

    def test_mixed_valid_invalid(self):
        """Test mix of valid and invalid."""
        jam_mulai, jam_selesai, jam_display, warnings = convert_waktu("1/2/99")
        assert jam_mulai == "07:30"
        assert jam_selesai == "09:30"
        assert len(warnings) > 0

    def test_empty_string(self):
        """Test empty string."""
        jam_mulai, jam_selesai, jam_display, warnings = convert_waktu("")
        assert jam_mulai is None
        assert jam_selesai is None
        assert len(warnings) > 0


class TestJadwalKuliahTable:
    """Test the JADWAL_KULIAH reference table."""

    def test_table_has_14_entries(self):
        """Table should have exactly 14 slots."""
        assert len(JADWAL_KULIAH) == 14

    def test_all_slots_present(self):
        """All slots 1-14 should be present."""
        for i in range(1, 15):
            assert i in JADWAL_KULIAH

    def test_slot_format(self):
        """Each slot should have (start_time, end_time) tuple."""
        for slot, (start, end) in JADWAL_KULIAH.items():
            assert isinstance(start, str)
            assert isinstance(end, str)
            assert ":" in start
            assert ":" in end

    def test_consecutive_time_ranges(self):
        """Each slot should be 1 hour, and no gaps."""
        for i in range(1, 14):
            end_current = JADWAL_KULIAH[i][1]
            start_next = JADWAL_KULIAH[i + 1][0]
            assert end_current == start_next, f"Gap between slot {i} and {i+1}"
