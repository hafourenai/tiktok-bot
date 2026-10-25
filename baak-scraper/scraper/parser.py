"""Parse BAAK HTML schedule data."""

import logging
from typing import List, Optional
from bs4 import BeautifulSoup

from .models import Jadwal
from .converter import convert_waktu


logger = logging.getLogger(__name__)

# Common BAAK day names
VALID_DAYS = {"Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"}


class BAAKParser:
    """Parse BAAK HTML schedule pages."""

    @staticmethod
    def normalize_text(text: str) -> str:
        """Clean and normalize text."""
        if not text:
            return ""
        return " ".join(text.strip().split())

    @staticmethod
    def parse_schedule_html(html_content: str, target_kelas: Optional[str] = None) -> List[Jadwal]:
        """
        Parse BAAK schedule HTML using BeautifulSoup.
        
        Args:
            html_content: Raw HTML from BAAK
            target_kelas: Filter to specific class (optional)
            
        Returns:
            List of Jadwal objects
        """
        if not html_content:
            logger.warning("Empty HTML content")
            return []
        
        try:
            soup = BeautifulSoup(html_content, "html.parser")
        except Exception as e:
            logger.error(f"Failed to parse HTML: {e}")
            return []
        
        jadwal_list = []
        
        # Find all table rows containing schedule data
        rows = soup.find_all("tr")
        
        if not rows:
            logger.warning("No table rows found in HTML")
            return []
        
        for row in rows:
            cells = row.find_all("td")
            
            # Skip rows with insufficient columns (usually header/footer)
            if len(cells) < 6:
                continue
            
            # Extract data from cells
            try:
                kelas = BAAKParser.normalize_text(cells[0].get_text())
                hari = BAAKParser.normalize_text(cells[1].get_text())
                mata_kuliah = BAAKParser.normalize_text(cells[2].get_text())
                waktu = BAAKParser.normalize_text(cells[3].get_text())
                ruang = BAAKParser.normalize_text(cells[4].get_text()) if len(cells) > 4 else None
                dosen = BAAKParser.normalize_text(cells[5].get_text()) if len(cells) > 5 else None
                
                # Validate minimal required fields
                if not kelas or not hari or not mata_kuliah or not waktu:
                    continue
                
                # Filter by target class if specified
                if target_kelas and kelas.upper() != target_kelas.upper():
                    continue
                
                # Validate day
                if hari not in VALID_DAYS:
                    logger.debug(f"Skipping invalid day: {hari}")
                    continue
                
                # Convert time notation
                jam_mulai, jam_selesai, jam_display, time_warnings = convert_waktu(waktu)
                
                # Build Jadwal object
                jadwal = Jadwal(
                    kelas=kelas,
                    hari=hari,
                    mata_kuliah=mata_kuliah,
                    waktu=waktu,
                    jam_mulai=jam_mulai,
                    jam_selesai=jam_selesai,
                    jam=jam_display,
                    ruang=ruang if ruang and ruang.upper() != "N/A" else None,
                    dosen=dosen if dosen and dosen.upper() != "N/A" else None,
                    warnings=time_warnings,
                )
                
                jadwal_list.append(jadwal)
                
            except Exception as e:
                logger.debug(f"Failed to parse row: {e}")
                continue
        
        logger.info(f"Parsed {len(jadwal_list)} schedule entries")
        return jadwal_list

    @staticmethod
    def sort_jadwal(jadwal_list: List[Jadwal]) -> List[Jadwal]:
        """Sort schedule by day then start time."""
        day_order = {"Senin": 0, "Selasa": 1, "Rabu": 2, "Kamis": 3, "Jumat": 4, "Sabtu": 5, "Minggu": 6}
        
        def sort_key(j: Jadwal):
            day_idx = day_order.get(j.hari, 99)
            # Use jam_mulai if available, else put at end of day
            time_key = j.jam_mulai or "99:99"
            return (day_idx, time_key)
        
        return sorted(jadwal_list, key=sort_key)

    @staticmethod
    def filter_by_day(jadwal_list: List[Jadwal], hari: str) -> List[Jadwal]:
        """Filter schedule by day."""
        return [j for j in jadwal_list if j.hari.lower() == hari.lower()]

    @staticmethod
    def filter_by_subject(jadwal_list: List[Jadwal], keyword: str) -> List[Jadwal]:
        """Filter schedule by partial subject name match."""
        keyword_lower = keyword.lower()
        return [j for j in jadwal_list if keyword_lower in j.mata_kuliah.lower()]
