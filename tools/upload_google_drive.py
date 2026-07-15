from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Iterable
from zoneinfo import ZoneInfo

CAMBODIA_TZ = ZoneInfo("Asia/Phnom_Penh")
DAILY_DATE = re.compile(r"(?P<date>20\d{2}-\d{2}-\d{2})")
MONTH_VALUE = re.compile(r"(?P<month>20\d{2}-\d{2})(?!-\d{2})")


@dataclass(frozen=True)
class UploadItem:
    source: str
    destination: str
    size_bytes: int
    sha256: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _extract_date(name: str) -> datetime | None:
    match = DAILY_DATE.search(name)
    if not match:
        return None
    try:
        return datetime.strptime(match.group("date"), "%Y-%m-%d")
    except ValueError:
        return None


def _extract_month(name: str) -> datetime | None:
    match = MONTH_VALUE.search(name)
    if not match:
        return None
    try:
        return datetime.strptime(match.group("month"), "%Y-%m")
    except ValueError:
        return None


def destination_for(path: Path, data_root: Path) -> PurePosixPath:
    """Return deterministic Google Drive path based on report filename/date."""
    relative = path.relative_to(data_root)
    top = relative.parts[0].lower() if relative.parts else "unclassified"
    name = path.name

    if top == "daily":
        day = _extract_date(name)
        if day:
            return PurePosixPath("daily", f"{day:%Y}", f"{day:%m}", f"{day:%d}", name)
    elif top == "weekly":
        day = _extract_date(name)
        if day:
            iso_year, iso_week, _ = day.isocalendar()
            return PurePosixPath("weekly", str(iso_year), f"W{iso_week:02d}", name)
    elif top == "monthly":
        month = _extract_month(name)
        if month:
            return PurePosixPath("monthly", f"{month:%Y}", f"{month:%m}", name)
    elif top == "qa":
        day = _extract_date(name)
        if day:
            return PurePosixPath("qa", f"{day:%Y}", f"{day:%m}", f"{day:%d}", name)
    elif top == "raw_archive":
        day = _extract_date(name)
        if day:
            return PurePosixPath("raw_archive", f"{day:%Y}", f"{day:%m}", f"{day:%d}", name)
    elif top == "logs":
        day = _extract_date(name)
        if day:
            return PurePosixPath("logs", f"{day:%Y}", f"{day:%m}", name)
        month = _extract_month(name)
        if month:
            return PurePosixPath("logs", f"{month:%Y}", f"{month:%m}", name)
    elif top == "master":
        return PurePosixPath("master", name)
    elif top == "master_backups":
        day = _extract_date(name)
        if day:
            return PurePosixPath("master_backups", f"{day:%Y}", f"{day:%m}", name)
        return PurePosixPath("master_backups", name)

    return PurePosixPath("unclassified", *relative.parts)


def iter_files(data_root: Path, categories: Iterable[str]) -> list[Path]:
    files: list[Path] = []
    for category in categories:
        folder = data_root / category
        if not folder.exists():
            continue
        files.extend(
            p for p in folder.rglob("*")
            if p.is_file() and p.name != ".gitkeep" and p.stat().st_size > 0
        )
    return sorted(set(files))


def _run(command: list[str]) -> None:
    print("$", " ".join(command))
    subprocess.run(command, check=True)


def _upload_file(source: Path, remote: str, remote_root: str, destination: PurePosixPath, dry_run: bool) -> None:
    target = f"{remote}:{PurePosixPath(remote_root) / destination}"
    command = [
        "rclone", "copyto", str(source), target,
        "--checksum", "--create-empty-src-dirs",
        "--retries", "3", "--low-level-retries", "10",
        "--timeout", "5m", "--contimeout", "30s",
        "--log-level", "INFO",
    ]
    if dry_run:
        command.append("--dry-run")
    _run(command)


def _write_manifest(items: list[UploadItem], workflow: str, run_id: str) -> Path:
    now = datetime.now(CAMBODIA_TZ)
    payload = {
        "system": "PEARL News Data Platform",
        "version": "5.0",
        "workflow": workflow,
        "github_run_id": run_id,
        "uploaded_at_cambodia": now.isoformat(),
        "file_count": len(items),
        "files": [asdict(item) for item in items],
    }
    temp_dir = Path(tempfile.mkdtemp(prefix="pearl_manifest_"))
    path = temp_dir / f"manifest_{workflow}_{now:%Y%m%d_%H%M%S}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Upload PEARL outputs directly to Google Drive using rclone.")
    parser.add_argument("--data-root", default=os.getenv("PEARL_DATA_ROOT", "data"))
    parser.add_argument("--remote", default=os.getenv("RCLONE_REMOTE_NAME", "pearl-drive"))
    parser.add_argument("--remote-root", default=os.getenv("GOOGLE_DRIVE_ROOT", "PEARL-News-Archive"))
    parser.add_argument("--workflow", choices=("daily", "weekly", "monthly", "all"), default="all")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if shutil.which("rclone") is None:
        print("ERROR: rclone is not installed or not on PATH.", file=sys.stderr)
        return 2

    data_root = Path(args.data_root).resolve()
    category_map = {
        "daily": ("daily", "qa", "logs", "raw_archive", "master", "master_backups"),
        "weekly": ("weekly", "logs", "master"),
        "monthly": ("monthly", "logs", "master"),
        "all": ("daily", "weekly", "monthly", "qa", "logs", "raw_archive", "master", "master_backups"),
    }
    files = iter_files(data_root, category_map[args.workflow])
    if not files:
        print(f"ERROR: No output files found under {data_root} for workflow={args.workflow}.", file=sys.stderr)
        return 3

    print(f"PEARL Google Drive upload v5.0")
    print(f"Data root  : {data_root}")
    print(f"Destination: {args.remote}:{args.remote_root}")
    print(f"Workflow   : {args.workflow}")
    print(f"Files      : {len(files)}")

    items: list[UploadItem] = []
    for source in files:
        destination = destination_for(source, data_root)
        _upload_file(source, args.remote, args.remote_root, destination, args.dry_run)
        items.append(
            UploadItem(
                source=str(source.relative_to(data_root)),
                destination=str(destination),
                size_bytes=source.stat().st_size,
                sha256=_sha256(source),
            )
        )

    manifest = _write_manifest(items, args.workflow, os.getenv("GITHUB_RUN_ID", "local"))
    manifest_destination = PurePosixPath(
        "manifests", args.workflow,
        f"{datetime.now(CAMBODIA_TZ):%Y}",
        f"{datetime.now(CAMBODIA_TZ):%m}",
        manifest.name,
    )
    _upload_file(manifest, args.remote, args.remote_root, manifest_destination, args.dry_run)
    print(f"SUCCESS: Uploaded {len(items)} files plus manifest.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

