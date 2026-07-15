from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

DATE_PATTERN = re.compile(r"(?<!\d)(20\d{2})-(\d{2})-(\d{2})(?!\d)")
MONTH_PATTERN = re.compile(r"(?<!\d)(20\d{2})-(\d{2})(?!-?\d)")


def daily_destination(root: Path, category: str, filename: str) -> Path | None:
    match = DATE_PATTERN.search(filename)
    if not match:
        return None
    year, month, day = match.groups()
    if category == "logs":
        return root / "logs" / year / month
    return root / category / year / month / day


def monthly_destination(root: Path, filename: str) -> Path | None:
    match = MONTH_PATTERN.search(filename)
    if not match:
        return None
    year, month = match.groups()
    return root / "monthly" / year / month


def unique_target(destination: Path) -> Path:
    if not destination.exists():
        return destination
    counter = 2
    while True:
        candidate = destination.with_name(
            f"{destination.stem}_migrated_{counter}{destination.suffix}"
        )
        if not candidate.exists():
            return candidate
        counter += 1


def repair(root: Path, *, apply: bool) -> tuple[int, int]:
    planned = moved = 0
    categories = ("daily", "qa", "raw_archive", "logs")

    for category in categories:
        base = root / category
        if not base.exists():
            continue
        for source in list(base.rglob("*")):
            if not source.is_file():
                continue
            destination_dir = daily_destination(root, category, source.name)
            if destination_dir is None:
                continue
            destination = destination_dir / source.name
            if source.resolve() == destination.resolve():
                continue
            planned += 1
            print(f"{'MOVE' if apply else 'PLAN'}: {source} -> {destination}")
            if apply:
                destination_dir.mkdir(parents=True, exist_ok=True)
                final = unique_target(destination)
                shutil.move(str(source), str(final))
                moved += 1

    monthly_base = root / "monthly"
    if monthly_base.exists():
        for source in list(monthly_base.rglob("*")):
            if not source.is_file():
                continue
            destination_dir = monthly_destination(root, source.name)
            if destination_dir is None:
                continue
            destination = destination_dir / source.name
            if source.resolve() == destination.resolve():
                continue
            planned += 1
            print(f"{'MOVE' if apply else 'PLAN'}: {source} -> {destination}")
            if apply:
                destination_dir.mkdir(parents=True, exist_ok=True)
                final = unique_target(destination)
                shutil.move(str(source), str(final))
                moved += 1

    return planned, moved


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Repair PEARL archive folders using report dates in filenames."
    )
    parser.add_argument(
        "--archive-root",
        default=r"D:\001_GitHub\PEARL-News-Archive",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Move files. Without this flag the tool only previews changes.",
    )
    args = parser.parse_args()

    root = Path(args.archive_root)
    if not root.exists():
        raise FileNotFoundError(f"Archive root does not exist: {root}")

    planned, moved = repair(root, apply=args.apply)
    print(f"Planned corrections: {planned}")
    print(f"Files moved: {moved}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
