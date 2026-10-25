"""Demo script showing scraper functionality with fixtures."""

import sys
from pathlib import Path
import json

# Add scraper to path
sys.path.insert(0, str(Path(__file__).parent))

from scraper.parser import BAAKParser
from scraper.models import ScheduleResponse, Jadwal


def demo():
    """Run demo with sample fixture HTML."""
    
    # Load sample HTML
    fixture_path = Path(__file__).parent / "tests" / "fixtures" / "sample_baak.html"
    with open(fixture_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    
    print("\n" + "="*120)
    print("BAAK Schedule Scraper - Demo dengan Sample Fixture")
    print("="*120 + "\n")
    
    # Parse all
    print("[1] Parse semua jadwal dari fixture...")
    all_jadwal = BAAKParser.parse_schedule_html(html_content)
    print(f"    FOUND: {len(all_jadwal)} entries\n")
    
    # Parse specific class
    print("[2] Parse untuk kelas 3KA01 saja...")
    kelas_3ka01 = BAAKParser.parse_schedule_html(html_content, target_kelas="3KA01")
    print(f"    FOUND: {len(kelas_3ka01)} entries untuk 3KA01\n")
    
    # Show extracted data
    print("[3] Tampilkan data ekstrak (7 kolom inti):")
    print(f"{'Kelas':<10} {'Hari':<12} {'Mata Kuliah':<35} {'Waktu':<8} {'Jam':<20} {'Ruang':<15} {'Dosen':<20}")
    print("-"*120)
    for j in BAAKParser.sort_jadwal(kelas_3ka01):
        print(f"{j.kelas:<10} {j.hari:<12} {j.mata_kuliah:<35} {j.waktu:<8} {j.jam:<20} {j.ruang or 'N/A':<15} {j.dosen or 'N/A':<20}")
    
    print("\n" + "="*120)
    print("[4] Filter by Hari: Senin")
    print("="*120)
    senin = BAAKParser.filter_by_day(kelas_3ka01, "Senin")
    print(f"{'Kelas':<10} {'Hari':<12} {'Mata Kuliah':<35} {'Waktu':<8} {'Jam':<20} {'Ruang':<15} {'Dosen':<20}")
    print("-"*120)
    for j in BAAKParser.sort_jadwal(senin):
        print(f"{j.kelas:<10} {j.hari:<12} {j.mata_kuliah:<35} {j.waktu:<8} {j.jam:<20} {j.ruang or 'N/A':<15} {j.dosen or 'N/A':<20}")
    
    print("\n" + "="*120)
    print("[5] Filter by Subject: 'Basis Data'")
    print("="*120)
    basis_data = BAAKParser.filter_by_subject(kelas_3ka01, "Basis Data")
    print(f"{'Kelas':<10} {'Hari':<12} {'Mata Kuliah':<35} {'Waktu':<8} {'Jam':<20} {'Ruang':<15} {'Dosen':<20}")
    print("-"*120)
    for j in basis_data:
        print(f"{j.kelas:<10} {j.hari:<12} {j.mata_kuliah:<35} {j.waktu:<8} {j.jam:<20} {j.ruang or 'N/A':<15} {j.dosen or 'N/A':<20}")
    
    # Show JSON response
    print("\n" + "="*120)
    print("[6] API Response (JSON)")
    print("="*120 + "\n")
    
    response = ScheduleResponse(
        success=True,
        kelas="3KA01",
        semester="PTA 2026/2027",
        jadwal=BAAKParser.sort_jadwal(kelas_3ka01),
        fetched_at="2026-10-25T01:28:00+07:00",
        is_stale=False,
        status="ok",
    )
    
    print(json.dumps(response.to_dict(), ensure_ascii=False, indent=2))
    
    print("\n" + "="*120)
    print("SUCCESS: Demo completed!")
    print("="*120 + "\n")


if __name__ == "__main__":
    demo()
