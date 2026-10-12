"""Workspace and cleanup management for document conversions."""

import logging
import shutil
import tempfile
import time
from pathlib import Path

logger = logging.getLogger(__name__)

WORKSPACE_NAME = "bot_honey_converter"
STALE_WORKSPACE_SECONDS = 3600


def get_workspace() -> Path:
    """Get root directory for conversion workspaces."""
    return Path(tempfile.gettempdir()) / WORKSPACE_NAME


def new_workspace(prefix: str = "run-") -> str:
    """Create a fresh workspace directory for one conversion."""
    workspace = get_workspace()
    workspace.mkdir(parents=True, exist_ok=True)
    return tempfile.mkdtemp(prefix=prefix, dir=str(workspace))


def cleanup_stale_workspaces(max_age: int = STALE_WORKSPACE_SECONDS) -> list:
    """Delete leftover workspaces from crashed runs.
    
    Only directories inside :func:`get_workspace` older than ``max_age`` seconds
    are considered, so this is safe to call at startup even with concurrent conversions.
    """
    workspace = get_workspace()
    if not workspace.is_dir():
        return []
    
    removed = []
    cutoff = time.time() - max_age
    
    for entry in sorted(workspace.iterdir()):
        try:
            if not entry.is_dir():
                continue
            if entry.stat().st_mtime >= cutoff:
                continue
            shutil.rmtree(entry, ignore_errors=True)
            if entry.exists():
                continue
            removed.append(entry.name)
            logger.debug("Workspace dihapus: %s", entry.name)
        except OSError as e:
            logger.warning("Gagal menghapus workspace %s: %s", entry.name, e)
            continue
    
    if removed:
        logger.info("Membersihkan %d workspace konversi sisa: %s",
                   len(removed), ", ".join(removed[:5]))
    return removed
