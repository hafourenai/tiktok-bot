"""Data models for BAAK schedule."""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class Jadwal:
    """Single schedule entry."""
    kelas: str
    hari: str
    mata_kuliah: str
    waktu: str  # notasi slot, e.g. "1/2"
    jam_mulai: Optional[str] = None  # "07:30"
    jam_selesai: Optional[str] = None  # "09:30"
    jam: Optional[str] = None  # "07.30–09.30 WIB"
    ruang: Optional[str] = None
    dosen: Optional[str] = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self):
        """Convert to dict for JSON serialization."""
        return {
            "kelas": self.kelas,
            "hari": self.hari,
            "mata_kuliah": self.mata_kuliah,
            "waktu": self.waktu,
            "jam_mulai": self.jam_mulai,
            "jam_selesai": self.jam_selesai,
            "jam": self.jam,
            "ruang": self.ruang if self.ruang else "Belum tersedia",
            "dosen": self.dosen if self.dosen else "Belum tersedia",
            "warnings": self.warnings,
        }


@dataclass
class ScheduleResponse:
    """API response structure."""
    success: bool
    kelas: str
    semester: Optional[str] = None
    jadwal: list[Jadwal] = field(default_factory=list)
    source_name: str = "BAAK Gunadarma"
    source_url: str = "https://baak.gunadarma.ac.id/"
    source_mode: str = "verified_snapshot"  # or "official_public"
    fetched_at: Optional[str] = None
    is_stale: bool = False
    status: str = "ok"  # ok, stale, unavailable
    error: Optional[dict] = None

    def to_dict(self):
        """Convert to dict for JSON serialization."""
        return {
            "success": self.success,
            "kelas": self.kelas,
            "semester": self.semester,
            "data": [j.to_dict() for j in self.jadwal],
            "meta": {
                "source_name": self.source_name,
                "source_url": self.source_url,
                "source_mode": self.source_mode,
                "fetched_at": self.fetched_at,
                "is_stale": self.is_stale,
                "status": self.status,
            },
            **({"error": self.error} if self.error else {}),
        }
