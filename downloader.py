import logging
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen

import yt_dlp

logger = logging.getLogger(__name__)


def download_tiktok(url: str, quality: str = "normal") -> Path:
    """Download one TikTok video and return its temporary local path."""
    from config import DOWNLOAD_DIR

    download_dir = Path(DOWNLOAD_DIR)
    download_dir.mkdir(parents=True, exist_ok=True)
    if quality == "hd":
        video_format = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
    else:
        video_format = "best[height<=720][ext=mp4]/best[height<=720]/best[ext=mp4]/best"

    options = {
        "format": video_format,
        "outtmpl": str(download_dir / f"%(id)s-{quality}.%(ext)s"),
        "noplaylist": True,
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
    }
    logger.info("Download started")
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = Path(ydl.prepare_filename(info))
    result = filename.with_suffix(".mp4")
    if not result.exists():
        result = filename
    if not result.exists():
        raise FileNotFoundError("yt-dlp did not produce a video file")
    logger.info("Download completed")
    return result


def download_with_gallery_dl(url: str) -> Path:
    """Try gallery-dl as a no-key fallback for public TikTok URLs."""
    from config import DOWNLOAD_DIR

    download_dir = Path(DOWNLOAD_DIR)
    download_dir.mkdir(parents=True, exist_ok=True)
    work_dir = Path(tempfile.mkdtemp(prefix="gallery-", dir=download_dir))
    try:
        command = [sys.executable, "-m", "gallery_dl", "-d", str(work_dir), url]
        result = subprocess.run(command, capture_output=True, text=True, timeout=300, check=False)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "gallery-dl failed")
        files = [item for item in work_dir.rglob("*") if item.is_file() and item.suffix.lower() in {".mp4", ".mkv", ".webm", ".mov"}]
        if not files:
            raise FileNotFoundError("gallery-dl did not produce a video file")
        target = download_dir / f"gallery-{files[0].name}"
        shutil.move(str(files[0]), target)
        return target
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def cleanup_downloads(directory: str) -> None:
    """Remove leftover files from previous interrupted downloads."""
    path = Path(directory)
    if not path.exists():
        return
    for item in path.iterdir():
        if item.is_file():
            item.unlink(missing_ok=True)


def download_with_tiktok_api_dl(url: str) -> Path:
    """Use the selected unofficial Node.js package as a final fallback."""
    from config import DOWNLOAD_DIR

    download_dir = Path(DOWNLOAD_DIR)
    download_dir.mkdir(parents=True, exist_ok=True)
    bridge = Path(__file__).with_name("tiktok_api_bridge.js")
    result = subprocess.run(
        ["node", str(bridge), url], capture_output=True, text=True, timeout=90, check=False
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "tiktok-api-dl failed")
    try:
        media_url = json.loads(result.stdout)["url"]
    except (json.JSONDecodeError, KeyError) as error:
        raise RuntimeError("tiktok-api-dl returned an invalid response") from error

    target = download_dir / "tiktok-api-dl.mp4"
    request = Request(media_url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.tiktok.com/"})
    with urlopen(request, timeout=300) as response, target.open("wb") as video:
        shutil.copyfileobj(response, video)
    if not target.exists() or target.stat().st_size == 0:
        target.unlink(missing_ok=True)
        raise FileNotFoundError("tiktok-api-dl did not produce a video file")
    return target


def stalk_tiktok_user(username: str) -> dict:
    """Fetch TikTok user profile information using the Node.js bridge."""
    bridge = Path(__file__).with_name("tiktok_api_bridge.js")
    result = subprocess.run(
        ["node", str(bridge), "stalk", username],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Gagal mengambil data profil TikTok")
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as err:
        raise RuntimeError("Respon profil TikTok tidak valid") from err

    if data.get("status") != "success" or "result" not in data:
        raise RuntimeError(data.get("message") or "Pengguna TikTok tidak ditemukan")
    return data["result"]


def get_tiktok_user_posts(username: str, limit: int = 5) -> list[dict]:
    """Fetch recent posts from a TikTok user using the Node.js bridge."""
    bridge = Path(__file__).with_name("tiktok_api_bridge.js")
    result = subprocess.run(
        ["node", str(bridge), "posts", username, str(limit)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Gagal mengambil postingan TikTok")
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as err:
        raise RuntimeError("Respon postingan TikTok tidak valid") from err

    if data.get("status") != "success" or not isinstance(data.get("result"), list):
        raise RuntimeError(data.get("message") or "Postingan TikTok tidak ditemukan")
    return data["result"]


def get_tiktok_user_reposts(username: str, limit: int = 5) -> list[dict]:
    """Fetch recent reposts from a TikTok user using the Node.js bridge."""
    bridge = Path(__file__).with_name("tiktok_api_bridge.js")
    result = subprocess.run(
        ["node", str(bridge), "reposts", username, str(limit)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Gagal mengambil repostan TikTok")
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as err:
        raise RuntimeError("Respon repostan TikTok tidak valid") from err

    if data.get("status") != "success" or not isinstance(data.get("result"), list):
        raise RuntimeError(data.get("message") or "Repostan TikTok tidak ditemukan")
    return data["result"]


def download_youtube(url: str, quality: str = "normal") -> Path:
    """Download one YouTube video and return its temporary local path."""
    from config import DOWNLOAD_DIR

    download_dir = Path(DOWNLOAD_DIR)
    download_dir.mkdir(parents=True, exist_ok=True)
    if quality == "hd":
        video_format = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
    else:
        video_format = "best[height<=720][ext=mp4]/best[height<=720]/best[ext=mp4]/best"

    options = {
        "format": video_format,
        "outtmpl": str(download_dir / f"%(id)s-{quality}.%(ext)s"),
        "noplaylist": True,
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
    }
    logger.info("YouTube download started")
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = Path(ydl.prepare_filename(info))
    result = filename.with_suffix(".mp4")
    if not result.exists():
        result = filename
    if not result.exists():
        raise FileNotFoundError("yt-dlp did not produce a video file")
    logger.info("YouTube download completed")
    return result
