"""Convert BAAK time slot notation to actual times."""

from typing import Optional, Tuple


# 14 jadwal kuliah resmi BAAK
JADWAL_KULIAH = {
    1: ("07:30", "08:30"),
    2: ("08:30", "09:30"),
    3: ("09:30", "10:30"),
    4: ("10:30", "11:30"),
    5: ("11:30", "12:30"),
    6: ("12:30", "13:30"),
    7: ("13:30", "14:30"),
    8: ("14:30", "15:30"),
    9: ("15:30", "16:30"),
    10: ("16:30", "17:30"),
    11: ("17:30", "18:30"),
    12: ("18:30", "19:30"),
    13: ("19:30", "20:30"),
    14: ("20:30", "21:30"),
}


def parse_waktu_slots(waktu: str) -> Tuple[Optional[list[int]], list[str]]:
    """
    Parse notasi waktu "1/2/3" into slot numbers.
    Returns (slot_list, warnings).
    """
    warnings = []
    
    if not waktu or not waktu.strip():
        warnings.append("Notasi waktu kosong")
        return None, warnings
    
    waktu = waktu.strip()
    parts = waktu.split("/")
    slots = []
    
    for part in parts:
        part = part.strip()
        try:
            slot = int(part)
            if slot < 1 or slot > 14:
                warnings.append(f"Slot {slot} di luar range 1-14")
                continue
            slots.append(slot)
        except ValueError:
            warnings.append(f"Slot '{part}' bukan angka")
            continue
    
    if not slots:
        return None, warnings if warnings else ["Tidak ada slot valid"]
    
    # Check if slots are consecutive
    if len(slots) > 1:
        slots_sorted = sorted(slots)
        for i in range(len(slots_sorted) - 1):
            if slots_sorted[i + 1] - slots_sorted[i] != 1:
                warnings.append(f"Slot tidak berurutan: {waktu}")
                break
    
    return sorted(slots), warnings


def convert_slots_to_time(slots: list[int]) -> Tuple[str, str, str]:
    """
    Convert slot numbers to start time, end time, and formatted display.
    Returns (jam_mulai, jam_selesai, jam_display).
    
    Example:
        [1, 2] -> ("07:30", "09:30", "07.30–09.30 WIB")
    """
    if not slots:
        return None, None, None
    
    min_slot = min(slots)
    max_slot = max(slots)
    
    jam_mulai = JADWAL_KULIAH[min_slot][0]
    jam_selesai = JADWAL_KULIAH[max_slot][1]
    
    # Format display dengan titik dan panjang en-dash
    jam_display = f"{jam_mulai.replace(':', '.')}–{jam_selesai.replace(':', '.')} WIB"
    
    return jam_mulai, jam_selesai, jam_display


def convert_waktu(waktu: str) -> Tuple[Optional[str], Optional[str], Optional[str], list[str]]:
    """
    Complete conversion from waktu notation to time range.
    Returns (jam_mulai, jam_selesai, jam_display, warnings).
    """
    slots, warnings = parse_waktu_slots(waktu)
    
    if slots is None:
        return None, None, None, warnings
    
    jam_mulai, jam_selesai, jam_display = convert_slots_to_time(slots)
    return jam_mulai, jam_selesai, jam_display, warnings


def get_all_jadwal_kuliah():
    """Get all 14 slots for reference/testing."""
    return JADWAL_KULIAH
