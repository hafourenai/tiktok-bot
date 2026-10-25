"""Main CLI for BAAK scraper."""

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any
from zoneinfo import ZoneInfo

from scraper.client import BAAKClient
from scraper.parser import BAAKParser
from scraper.models import ScheduleResponse, Jadwal


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Data directory for snapshots
DATA_DIR = Path(__file__).parent / "data"
SNAPSHOTS_DIR = DATA_DIR / "snapshots"
CACHE_TTL_SECONDS = 6 * 3600  # 6 hours

# In-memory cache
_cache: Dict[str, tuple[list[Jadwal], datetime]] = {}


def ensure_data_dirs():
    """Ensure data directories exist."""
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)


def get_wib_now() -> datetime:
    """Get current time in WIB (Asia/Jakarta)."""
    return datetime.now(ZoneInfo("Asia/Jakarta"))


def is_cache_valid(cached_time: datetime) -> bool:
    """Check if cache entry is still valid."""
    age = (get_wib_now() - cached_time).total_seconds()
    return age < CACHE_TTL_SECONDS


def load_snapshot(semester: str) -> Optional[list[Jadwal]]:
    """Load jadwal from snapshot file."""
    snapshot_file = SNAPSHOTS_DIR / f"{semester.replace('/', '_')}.json"
    
    if not snapshot_file.exists():
        logger.warning(f"Snapshot not found: {snapshot_file}")
        return None
    
    try:
        with open(snapshot_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Validate structure
        if not isinstance(data, dict) or "jadwal" not in data:
            logger.error("Invalid snapshot structure")
            return None
        
        # Reconstruct Jadwal objects
        jadwal_list = []
        for item in data["jadwal"]:
            jadwal = Jadwal(
                kelas=item.get("kelas"),
                hari=item.get("hari"),
                mata_kuliah=item.get("mata_kuliah"),
                waktu=item.get("waktu"),
                jam_mulai=item.get("jam_mulai"),
                jam_selesai=item.get("jam_selesai"),
                jam=item.get("jam"),
                ruang=item.get("ruang"),
                dosen=item.get("dosen"),
                warnings=item.get("warnings", []),
            )
            jadwal_list.append(jadwal)
        
        logger.info(f"Loaded {len(jadwal_list)} entries from snapshot")
        return jadwal_list
        
    except Exception as e:
        logger.error(f"Failed to load snapshot: {e}")
        return None


def save_snapshot(semester: str, jadwal_list: list[Jadwal], source_url: str):
    """Save jadwal to snapshot file."""
    snapshot_file = SNAPSHOTS_DIR / f"{semester.replace('/', '_')}.json"
    
    data = {
        "schema_version": "1.0",
        "semester": semester,
        "source_mode": "verified_snapshot",
        "source_url": source_url,
        "fetched_at": get_wib_now().isoformat(),
        "jadwal": [j.to_dict() for j in jadwal_list],
    }
    
    try:
        with open(snapshot_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved snapshot: {snapshot_file}")
    except Exception as e:
        logger.error(f"Failed to save snapshot: {e}")


def get_jadwal(
    kelas: str,
    semester: str = "PTA 2026/2027",
    force_refresh: bool = False,
) -> Optional[list[Jadwal]]:
    """
    Get jadwal for a class with caching.
    
    Priority:
    1. In-memory cache (if valid)
    2. Try fetch from BAAK
    3. Fall back to snapshot
    """
    cache_key = f"{kelas}:{semester}"
    
    # Check in-memory cache
    if not force_refresh and cache_key in _cache:
        jadwal_list, cached_time = _cache[cache_key]
        if is_cache_valid(cached_time):
            logger.info(f"Cache hit: {cache_key}")
            return jadwal_list
    
    # Try to fetch from BAAK
    client = BAAKClient()
    html = client.get("/")  # or specific endpoint
    
    if html and not client.is_cloudflare_error(html):
        jadwal_list = BAAKParser.parse_schedule_html(html, target_kelas=kelas)
        
        if jadwal_list:
            # Update in-memory cache
            _cache[cache_key] = (jadwal_list, get_wib_now())
            
            # Optionally save to snapshot (if requested)
            # save_snapshot(semester, jadwal_list, client.base_url)
            
            logger.info(f"Fetched {len(jadwal_list)} entries from BAAK")
            return jadwal_list
        else:
            logger.warning("No jadwal found for this class")
    else:
        logger.warning("Failed to fetch from BAAK or Cloudflare error detected")
    
    # Fall back to snapshot
    logger.info("Falling back to snapshot...")
    return load_snapshot(semester)


def build_response(
    kelas: str,
    jadwal_list: Optional[list[Jadwal]],
    semester: str,
    is_stale: bool = False,
) -> Dict[str, Any]:
    """Build API response structure."""
    if not jadwal_list:
        return {
            "success": False,
            "kelas": kelas,
            "error": {
                "code": "SOURCE_UNAVAILABLE",
                "message": "Jadwal tidak tersedia. Periksa kembali di BAAK.",
            },
        }
    
    # Sort by day then time
    sorted_jadwal = BAAKParser.sort_jadwal(jadwal_list)
    
    response = ScheduleResponse(
        success=True,
        kelas=kelas,
        semester=semester,
        jadwal=sorted_jadwal,
        fetched_at=get_wib_now().isoformat(),
        is_stale=is_stale,
        status="stale" if is_stale else "ok",
    )
    
    return response.to_dict()


def main():
    """Main CLI entry point."""
    ensure_data_dirs()
    
    parser = argparse.ArgumentParser(
        description="BAAK Schedule Scraper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --class 3KA01
  python main.py --class 3KA01 --hari Senin
  python main.py --class 3KA01 --subject "Basis Data"
  python main.py --validate-snapshots
  python main.py --clear-cache
        """,
    )
    
    parser.add_argument(
        "--class",
        dest="kelas",
        type=str,
        help="Kode kelas (e.g., 3KA01)",
    )
    parser.add_argument(
        "--semester",
        type=str,
        default="PTA 2026/2027",
        help="Semester (default: PTA 2026/2027)",
    )
    parser.add_argument(
        "--hari",
        type=str,
        help="Filter by day (Senin, Selasa, ...)",
    )
    parser.add_argument(
        "--subject",
        type=str,
        help="Filter by subject keyword",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Force refresh from BAAK (ignore cache)",
    )
    parser.add_argument(
        "--save-snapshot",
        action="store_true",
        help="Save fetched data to snapshot",
    )
    parser.add_argument(
        "--validate-snapshots",
        action="store_true",
        help="Validate all snapshots",
    )
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Clear in-memory cache",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="json",
        choices=["json", "table"],
        help="Output format",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose logging",
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Handle cache clear
    if args.clear_cache:
        _cache.clear()
        print("Cache cleared.")
        return 0
    
    # Handle snapshot validation
    if args.validate_snapshots:
        logger.info("Validating snapshots...")
        for snapshot_file in SNAPSHOTS_DIR.glob("*.json"):
            try:
                with open(snapshot_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                required_keys = {"schema_version", "semester", "jadwal"}
                if required_keys.issubset(data.keys()):
                    print(f"✓ {snapshot_file.name}: valid ({len(data['jadwal'])} entries)")
                else:
                    print(f"✗ {snapshot_file.name}: missing keys")
            except Exception as e:
                print(f"✗ {snapshot_file.name}: {e}")
        return 0
    
    # Handle schedule query
    if not args.kelas:
        parser.print_help()
        return 1
    
    # Normalize kelas
    kelas = args.kelas.strip().upper()
    
    # Get jadwal
    jadwal_list = get_jadwal(
        kelas=kelas,
        semester=args.semester,
        force_refresh=args.force_refresh,
    )
    
    # Apply filters
    if jadwal_list:
        if args.hari:
            jadwal_list = BAAKParser.filter_by_day(jadwal_list, args.hari)
        if args.subject:
            jadwal_list = BAAKParser.filter_by_subject(jadwal_list, args.subject)
    
    # Save snapshot if requested
    if args.save_snapshot and jadwal_list:
        save_snapshot(args.semester, jadwal_list, "https://baak.gunadarma.ac.id")
    
    # Build response
    is_stale = jadwal_list is not None and jadwal_list  # TODO: track staleness properly
    response = build_response(kelas, jadwal_list, args.semester, is_stale=False)
    
    # Output
    if args.output == "json":
        print(json.dumps(response, ensure_ascii=False, indent=2))
    elif args.output == "table":
        if response["success"] and response.get("data"):
            print(f"\n{'='*120}")
            print(f"Jadwal: {kelas} | Semester: {response.get('semester', 'N/A')}")
            print(f"{'='*120}")
            print(f"{'Hari':<12} {'Mata Kuliah':<35} {'Waktu':<8} {'Jam':<20} {'Ruang':<15} {'Dosen':<20}")
            print(f"{'-'*120}")
            
            for item in response["data"]:
                print(f"{item['hari']:<12} {item['mata_kuliah']:<35} {item['waktu']:<8} {item['jam']:<20} {item['ruang']:<15} {item['dosen']:<20}")
            
            print(f"{'='*120}\n")
        else:
            print(response.get("error", {}).get("message", "Tidak ada data"))
    
    return 0 if response["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
