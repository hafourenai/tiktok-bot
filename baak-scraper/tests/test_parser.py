"""Tests for BAAK HTML parser."""

import pytest
from scraper.parser import BAAKParser
from scraper.models import Jadwal


class TestBAAKParser:
    """Test BAAK HTML parsing."""

    def test_parse_sample_html(self, sample_baak_html):
        """Test parsing sample BAAK HTML."""
        jadwal_list = BAAKParser.parse_schedule_html(sample_baak_html)
        
        assert len(jadwal_list) > 0
        assert all(isinstance(j, Jadwal) for j in jadwal_list)

    def test_parse_3ka01_schedule(self, sample_baak_html):
        """Test parsing 3KA01 class schedule."""
        jadwal_list = BAAKParser.parse_schedule_html(sample_baak_html, target_kelas="3KA01")
        
        assert len(jadwal_list) >= 4
        assert all(j.kelas == "3KA01" for j in jadwal_list)

    def test_extracted_fields(self, sample_baak_html):
        """Test that all 7 fields are extracted correctly."""
        jadwal_list = BAAKParser.parse_schedule_html(sample_baak_html)
        
        first = jadwal_list[0]
        assert first.kelas == "3KA01"
        assert first.hari == "Senin"
        assert first.mata_kuliah == "Pemrograman Basis Data"
        assert first.waktu == "1/2"
        assert first.jam == "07.30–09.30 WIB"
        assert first.ruang == "RUANG 101"
        assert first.dosen == "Dr. Andi"

    def test_time_conversion_applied(self, sample_baak_html):
        """Test that time conversion is applied during parsing."""
        jadwal_list = BAAKParser.parse_schedule_html(sample_baak_html)
        
        # Find the 1/2 entry
        one_two = [j for j in jadwal_list if j.waktu == "1/2"][0]
        assert one_two.jam_mulai == "07:30"
        assert one_two.jam_selesai == "09:30"
        assert one_two.jam == "07.30–09.30 WIB"

    def test_na_fields_become_none(self, sample_baak_html):
        """Test that N/A fields are converted to None."""
        jadwal_list = BAAKParser.parse_schedule_html(sample_baak_html)
        
        # Find entry with N/A ruang
        no_ruang = [j for j in jadwal_list if j.mata_kuliah == "Kecerdasan Buatan"][0]
        assert no_ruang.ruang is None
        
        # Find entry with N/A dosen
        no_dosen = [j for j in jadwal_list if j.mata_kuliah == "Jaringan Komputer"][0]
        assert no_dosen.dosen is None

    def test_empty_html(self):
        """Test parsing empty HTML."""
        jadwal_list = BAAKParser.parse_schedule_html("")
        assert len(jadwal_list) == 0

    def test_minimal_html(self, sample_minimal_html):
        """Test parsing HTML with no schedule data."""
        jadwal_list = BAAKParser.parse_schedule_html(sample_minimal_html)
        assert len(jadwal_list) == 0

    def test_normalize_text(self):
        """Test text normalization."""
        assert BAAKParser.normalize_text("  hello  world  ") == "hello world"
        assert BAAKParser.normalize_text("") == ""
        assert BAAKParser.normalize_text(None) == ""

    def test_day_validation(self, sample_baak_html):
        """Test that invalid days are skipped."""
        jadwal_list_original = BAAKParser.parse_schedule_html(sample_baak_html)
        original_count = len(jadwal_list_original)
        
        # Modify HTML to include invalid day
        invalid_html = sample_baak_html.replace("Senin", "InvalidDay")
        jadwal_list = BAAKParser.parse_schedule_html(invalid_html)
        
        # Should have fewer entries (Senin entries removed)
        assert len(jadwal_list) < original_count


class TestSortJadwal:
    """Test schedule sorting."""

    def test_sort_by_day_then_time(self, sample_baak_html):
        """Test sorting by day then time."""
        jadwal_list = BAAKParser.parse_schedule_html(sample_baak_html)
        sorted_list = BAAKParser.sort_jadwal(jadwal_list)
        
        # First day should be Senin
        assert sorted_list[0].hari == "Senin"
        
        # Within same day, should be sorted by time
        senin_entries = [j for j in sorted_list if j.hari == "Senin"]
        for i in range(len(senin_entries) - 1):
            assert senin_entries[i].jam_mulai <= senin_entries[i + 1].jam_mulai

    def test_sort_order(self, sample_baak_html):
        """Test day order: Senin->Minggu."""
        jadwal_list = BAAKParser.parse_schedule_html(sample_baak_html)
        sorted_list = BAAKParser.sort_jadwal(jadwal_list)
        
        days_in_order = [j.hari for j in sorted_list]
        # Fixture has: 2x Senin (3KA01), 1x Senin (3KB02), Selasa, Rabu, Kamis, Jumat, 1x Jumat (3KB02)
        # So expect 3 Senin entries first, then other days
        assert days_in_order[0] == "Senin"
        assert days_in_order.count("Senin") >= 2
        # Days should be in order: Senin < Selasa < Rabu < Kamis < Jumat
        assert all(days_in_order[i] <= days_in_order[i+1] or 
                   {"Senin": 0, "Selasa": 1, "Rabu": 2, "Kamis": 3, "Jumat": 4}.get(days_in_order[i], 99) <= 
                   {"Senin": 0, "Selasa": 1, "Rabu": 2, "Kamis": 3, "Jumat": 4}.get(days_in_order[i+1], 99)
                   for i in range(len(days_in_order) - 1))


class TestFilterJadwal:
    """Test schedule filtering."""

    def test_filter_by_day(self, sample_baak_html):
        """Test filtering by day."""
        jadwal_list = BAAKParser.parse_schedule_html(sample_baak_html)
        
        senin = BAAKParser.filter_by_day(jadwal_list, "Senin")
        assert all(j.hari == "Senin" for j in senin)
        assert len(senin) >= 2

    def test_filter_by_subject(self, sample_baak_html):
        """Test filtering by subject keyword."""
        jadwal_list = BAAKParser.parse_schedule_html(sample_baak_html)
        
        db_subjects = BAAKParser.filter_by_subject(jadwal_list, "Basis Data")
        assert len(db_subjects) == 1
        assert db_subjects[0].mata_kuliah == "Pemrograman Basis Data"

    def test_filter_by_subject_case_insensitive(self, sample_baak_html):
        """Test subject filter is case-insensitive."""
        jadwal_list = BAAKParser.parse_schedule_html(sample_baak_html)
        
        result1 = BAAKParser.filter_by_subject(jadwal_list, "basis data")
        result2 = BAAKParser.filter_by_subject(jadwal_list, "BASIS DATA")
        
        assert len(result1) == len(result2)
        assert result1 == result2
