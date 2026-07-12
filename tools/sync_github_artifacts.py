from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.archive.manager import archive_files, ensure_archive_tree

WORKFLOW_MAP = {
    "PEARL Daily News Collection v4.1": "daily",
    "PEARL Weekly Report v4.1": "weekly",
    "PEARL Monthly Report v4.1": "monthly",
}


def _run_gh(args: list[str]) -> str:
    if shutil.which("gh") is None:
        raise RuntimeError("GitHub CLI (gh) is not installed or is not on PATH.")
    completed = subprocess.run(["gh", *args], check=True, text=True, capture_output=True)
    return completed.stdout


def _copy_tree(source: Path, root: Path) -> int:
    count = 0
    for file in source.rglob("*"):
        if not file.is_file():
            continue
        parts = {part.lower() for part in file.parts}
        if "daily" in parts:
            destination = root / "daily" / f"{datetime.now():%Y}" / f"{datetime.now():%m}" / f"{datetime.now():%d}"
        elif "weekly" in parts:
            year, week, _ = datetime.now().isocalendar()
            destination = root / "weekly" / str(year) / f"W{week:02d}"
        elif "monthly" in parts:
            destination = root / "monthly" / f"{datetime.now():%Y}" / f"{datetime.now():%m}"
        elif "qa" in parts:
            destination = root / "qa" / f"{datetime.now():%Y}" / f"{datetime.now():%m}" / f"{datetime.now():%d}"
        elif "raw_archive" in parts:
            destination = root / "raw_archive" / f"{datetime.now():%Y}" / f"{datetime.now():%m}" / f"{datetime.now():%d}"
        elif "logs" in parts:
            destination = root / "logs" / f"{datetime.now():%Y}" / f"{datetime.now():%m}"
        elif "master_backups" in parts:
            destination = root / "master_backups" / f"{datetime.now():%Y}" / f"{datetime.now():%m}"
        elif "master" in parts and file.name == "PEARL_master_news.csv":
            destination = root / "master"
        else:
            destination = root / "sync_state" / "unclassified"
        archive_files([file], destination)
        count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Download successful PEARL GitHub artifacts to the local archive.")
    parser.add_argument("--repo", default="Mardy168/PEARL-Data-Platform")
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args()
    root = ensure_archive_tree()
    state_file = root / "sync_state" / "downloaded_runs.json"
    downloaded = set(json.loads(state_file.read_text(encoding="utf-8"))) if state_file.exists() else set()
    raw = _run_gh(["run", "list", "--repo", args.repo, "--limit", "100", "--json", "databaseId,workflowName,conclusion,createdAt,headBranch"])
    runs = json.loads(raw)
    cutoff = datetime.now(timezone.utc) - timedelta(days=args.days)
    added = 0
    for run in reversed(runs):
        run_id = str(run["databaseId"])
        if run_id in downloaded or run.get("conclusion") != "success":
            continue
        created = datetime.fromisoformat(run["createdAt"].replace("Z", "+00:00"))
        if created < cutoff or run.get("workflowName") not in WORKFLOW_MAP:
            continue
        with tempfile.TemporaryDirectory(prefix=f"pearl_{run_id}_") as tmp:
            target = Path(tmp)
            try:
                _run_gh(["run", "download", run_id, "--repo", args.repo, "--dir", str(target)])
            except subprocess.CalledProcessError as exc:
                print(f"Skipped run {run_id}: artifact download failed: {exc.stderr.strip()}")
                continue
            added += _copy_tree(target, root)
        downloaded.add(run_id)
    state_file.write_text(json.dumps(sorted(downloaded), indent=2), encoding="utf-8")
    print(f"Artifact synchronization completed. {added} files copied to {root}.")


if __name__ == "__main__":
    main()
