from __future__ import annotations

import hashlib
import os
import shutil
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from src.utils.dates import CAMBODIA_TZ

DEFAULT_WINDOWS_ARCHIVE = Path(r"D:\001_GitHub\PEARL-News-Archive")
ARCHIVE_SUBFOLDERS = (
    "daily", "weekly", "monthly", "master", "master_backups",
    "qa", "raw_archive", "logs", "monthly_zip", "sync_state",
)


@dataclass(frozen=True)
class ArchiveResult:
    enabled: bool
    root: Path | None
    copied: tuple[Path, ...]
    message: str


def archive_root() -> Path | None:
    """Return the configured local archive root, or None on GitHub/Linux.

    PEARL_ARCHIVE_ROOT is intentionally not configured in GitHub Actions because
    a GitHub-hosted runner cannot access a Windows D: drive. Local runs and the
    local artifact-sync task use the Windows environment variable.
    """
    configured = os.getenv("PEARL_ARCHIVE_ROOT", "").strip()
    if configured:
        return Path(configured).expanduser()
    if os.name == "nt":
        return DEFAULT_WINDOWS_ARCHIVE
    return None


def ensure_archive_tree(root: Path | None = None) -> Path:
    target = root or archive_root()
    if target is None:
        raise RuntimeError("PEARL_ARCHIVE_ROOT is not configured for this environment.")
    target.mkdir(parents=True, exist_ok=True)
    for name in ARCHIVE_SUBFOLDERS:
        (target / name).mkdir(parents=True, exist_ok=True)
    return target


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _copy_preserving_history(source: Path, destination_dir: Path) -> Path:
    """Copy a file without silently replacing a different historical file."""
    destination_dir.mkdir(parents=True, exist_ok=True)
    target = destination_dir / source.name
    if target.exists():
        if target.stat().st_size == source.stat().st_size and _sha256(target) == _sha256(source):
            return target
        stamp = datetime.now(CAMBODIA_TZ).strftime("%H%M%S")
        target = destination_dir / f"{source.stem}_{stamp}{source.suffix}"
        counter = 1
        while target.exists():
            target = destination_dir / f"{source.stem}_{stamp}_{counter}{source.suffix}"
            counter += 1
    shutil.copy2(source, target)
    return target


def archive_files(files: Iterable[str | Path], destination_dir: Path) -> tuple[Path, ...]:
    copied: list[Path] = []
    for item in files:
        source = Path(item)
        if source.is_file() and source.stat().st_size > 0:
            copied.append(_copy_preserving_history(source, destination_dir))
    return tuple(copied)


def archive_daily_run(
    *, report_date: str, daily_files: Iterable[str | Path], qa_files: Iterable[str | Path],
    log_files: Iterable[str | Path], raw_files: Iterable[str | Path], master_file: str | Path,
    backup_files: Iterable[str | Path] = (),
) -> ArchiveResult:
    root = archive_root()
    if root is None:
        return ArchiveResult(False, None, (), "Local archive skipped: no Windows archive root is accessible.")
    root = ensure_archive_tree(root)
    day = datetime.strptime(report_date, "%Y-%m-%d")
    copied: list[Path] = []
    copied += archive_files(daily_files, root / "daily" / f"{day:%Y}" / f"{day:%m}" / f"{day:%d}")
    copied += archive_files(qa_files, root / "qa" / f"{day:%Y}" / f"{day:%m}" / f"{day:%d}")
    copied += archive_files(raw_files, root / "raw_archive" / f"{day:%Y}" / f"{day:%m}" / f"{day:%d}")
    copied += archive_files(log_files, root / "logs" / f"{day:%Y}" / f"{day:%m}")
    copied += archive_files(backup_files, root / "master_backups" / f"{day:%Y}" / f"{day:%m}")
    master = Path(master_file)
    if master.is_file() and master.stat().st_size > 0:
        current = root / "master" / master.name
        current.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(master, current)
        copied.append(current)
    return ArchiveResult(True, root, tuple(copied), f"Archived {len(copied)} files to {root}")


def archive_weekly_run(*, report_date: str, files: Iterable[str | Path]) -> ArchiveResult:
    root = archive_root()
    if root is None:
        return ArchiveResult(False, None, (), "Local archive skipped: no Windows archive root is accessible.")
    root = ensure_archive_tree(root)
    day = datetime.strptime(report_date, "%Y-%m-%d")
    iso_year, iso_week, _ = day.isocalendar()
    copied = archive_files(files, root / "weekly" / str(iso_year) / f"W{iso_week:02d}")
    return ArchiveResult(True, root, copied, f"Archived {len(copied)} weekly files to {root}")


def archive_monthly_run(*, report_month: str, files: Iterable[str | Path]) -> ArchiveResult:
    root = archive_root()
    if root is None:
        return ArchiveResult(False, None, (), "Local archive skipped: no Windows archive root is accessible.")
    root = ensure_archive_tree(root)
    month = datetime.strptime(report_month, "%Y-%m")
    destination = root / "monthly" / f"{month:%Y}" / f"{month:%m}"
    copied = archive_files(files, destination)
    zip_dir = root / "monthly_zip" / f"{month:%Y}"
    zip_dir.mkdir(parents=True, exist_ok=True)
    zip_path = zip_dir / f"PEARL_monthly_archive_{report_month}.zip"
    temp_zip = zip_path.with_suffix(".tmp.zip")
    with zipfile.ZipFile(temp_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(destination.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(destination))
    temp_zip.replace(zip_path)
    return ArchiveResult(True, root, copied + (zip_path,), f"Archived monthly files and created {zip_path}")
