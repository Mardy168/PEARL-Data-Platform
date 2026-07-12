from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


CAMBODIA_TZ = ZoneInfo("Asia/Phnom_Penh")

DEFAULT_REPOSITORY = "Mardy168/PEARL-Data-Platform"
DEFAULT_ARCHIVE_ROOT = r"D:\001_GitHub\PEARL-News-Archive"

ALLOWED_BRANCHES = {
    "version-4.0",
    "version-4.1",
    "version-4.2",
}

WORKFLOW_MAP = {
    "PEARL Daily News Collection v4": "daily",
    "PEARL Daily News Collection v4.1": "daily",
    "PEARL Weekly Report v4": "weekly",
    "PEARL Weekly Report v4.1": "weekly",
    "PEARL Monthly Report v4": "monthly",
    "PEARL Monthly Report v4.1": "monthly",
}

RECOGNIZED_ARTIFACT_FOLDERS = {
    "daily",
    "weekly",
    "monthly",
    "master",
    "master_backups",
    "qa",
    "raw_archive",
    "logs",
    "monthly_zip",
}

STATE_FILENAME = "downloaded_runs.json"


@dataclass(frozen=True)
class WorkflowRun:
    run_id: int
    workflow_name: str
    category: str
    branch: str
    created_at: str
    updated_at: str


def _run_command(
    command: list[str],
    *,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        errors="replace",
    )

    if check and completed.returncode != 0:
        detail = (
            completed.stderr.strip()
            or completed.stdout.strip()
            or "Unknown command failure"
        )
        raise RuntimeError(
            f"Command failed with exit code {completed.returncode}: "
            f"{' '.join(command)}\n{detail}"
        )

    return completed


def _ensure_github_cli_ready() -> None:
    if shutil.which("gh") is None:
        raise RuntimeError(
            "GitHub CLI was not found. Install it with:\n"
            "winget install --id GitHub.cli"
        )

    _run_command(["gh", "auth", "status"])


def _github_api(endpoint: str) -> dict[str, Any]:
    completed = _run_command(
        [
            "gh",
            "api",
            "-H",
            "Accept: application/vnd.github+json",
            endpoint,
        ]
    )

    payload = completed.stdout.strip()
    if not payload:
        return {}

    try:
        result = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"GitHub API returned invalid JSON for endpoint: {endpoint}"
        ) from exc

    if not isinstance(result, dict):
        raise RuntimeError(
            f"Unexpected GitHub API response for endpoint: {endpoint}"
        )

    return result


def _ensure_archive_tree(root: Path) -> None:
    folders = [
        "daily",
        "weekly",
        "monthly",
        "master",
        "master_backups",
        "qa",
        "raw_archive",
        "logs",
        "monthly_zip",
        "sync_state",
    ]

    for folder in folders:
        (root / folder).mkdir(parents=True, exist_ok=True)


def _state_path(root: Path) -> Path:
    return root / "sync_state" / STATE_FILENAME


def _load_state(root: Path) -> dict[str, Any]:
    path = _state_path(root)

    if not path.exists():
        return {"runs": {}}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"runs": {}}

    if isinstance(data, list):
        return {
            "runs": {
                str(run_id): {
                    "legacy_entry": True,
                }
                for run_id in data
            }
        }

    if not isinstance(data, dict):
        return {"runs": {}}

    runs = data.get("runs")
    if not isinstance(runs, dict):
        data["runs"] = {}

    return data


def _save_state(root: Path, state: dict[str, Any]) -> None:
    path = _state_path(root)
    temporary_path = path.with_suffix(".tmp")

    temporary_path.write_text(
        json.dumps(
            state,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    temporary_path.replace(path)


def _parse_github_datetime(value: str) -> datetime:
    return datetime.fromisoformat(
        value.replace("Z", "+00:00")
    ).astimezone(CAMBODIA_TZ)


def _list_candidate_runs(
    repository: str,
    limit: int,
) -> list[WorkflowRun]:
    endpoint = (
        f"repos/{repository}/actions/runs"
        f"?status=completed&per_page={min(max(limit, 1), 100)}"
    )

    response = _github_api(endpoint)
    raw_runs = response.get("workflow_runs", [])

    if not isinstance(raw_runs, list):
        return []

    candidates: list[WorkflowRun] = []

    for item in raw_runs:
        if not isinstance(item, dict):
            continue

        workflow_name = str(item.get("name", "")).strip()
        branch = str(item.get("head_branch", "")).strip()
        conclusion = str(item.get("conclusion", "")).strip()

        if conclusion != "success":
            continue

        if workflow_name not in WORKFLOW_MAP:
            continue

        if branch not in ALLOWED_BRANCHES:
            continue

        run_id = item.get("id")
        if run_id is None:
            continue

        candidates.append(
            WorkflowRun(
                run_id=int(run_id),
                workflow_name=workflow_name,
                category=WORKFLOW_MAP[workflow_name],
                branch=branch,
                created_at=str(item.get("created_at", "")),
                updated_at=str(item.get("updated_at", "")),
            )
        )

    candidates.sort(
        key=lambda run: run.created_at,
        reverse=True,
    )

    return candidates


def _list_active_artifacts(
    repository: str,
    run_id: int,
) -> list[dict[str, Any]]:
    endpoint = (
        f"repos/{repository}/actions/runs/{run_id}/artifacts"
        "?per_page=100"
    )

    response = _github_api(endpoint)
    raw_artifacts = response.get("artifacts", [])

    if not isinstance(raw_artifacts, list):
        return []

    valid_artifacts: list[dict[str, Any]] = []

    for artifact in raw_artifacts:
        if not isinstance(artifact, dict):
            continue

        if bool(artifact.get("expired")):
            continue

        size = int(artifact.get("size_in_bytes", 0) or 0)
        if size <= 0:
            continue

        valid_artifacts.append(artifact)

    return valid_artifacts


def _download_run_artifacts(
    repository: str,
    run_id: int,
    destination: Path,
) -> None:
    if destination.exists():
        shutil.rmtree(destination)

    destination.mkdir(
        parents=True,
        exist_ok=True,
    )

    _run_command(
        [
            "gh",
            "run",
            "download",
            str(run_id),
            "--repo",
            repository,
            "--dir",
            str(destination),
        ]
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for block in iter(
            lambda: stream.read(1024 * 1024),
            b"",
        ):
            digest.update(block)

    return digest.hexdigest()


def _same_file(
    source: Path,
    destination: Path,
) -> bool:
    if not destination.exists():
        return False

    if source.stat().st_size != destination.stat().st_size:
        return False

    return _sha256(source) == _sha256(destination)


def _collision_safe_destination(
    source: Path,
    destination: Path,
) -> Path:
    if not destination.exists():
        return destination

    if _same_file(source, destination):
        return destination

    timestamp = datetime.now(
        CAMBODIA_TZ
    ).strftime("%Y%m%d_%H%M%S")

    candidate = destination.with_name(
        f"{destination.stem}_{timestamp}"
        f"{destination.suffix}"
    )

    counter = 2
    while candidate.exists():
        candidate = destination.with_name(
            f"{destination.stem}_{timestamp}_{counter}"
            f"{destination.suffix}"
        )
        counter += 1

    return candidate


def _copy_file(
    source: Path,
    destination: Path,
) -> bool:
    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    final_destination = _collision_safe_destination(
        source,
        destination,
    )

    if final_destination.exists() and _same_file(
        source,
        final_destination,
    ):
        return False

    shutil.copy2(
        source,
        final_destination,
    )

    return True


def _backup_existing_master(
    archive_root: Path,
    incoming_master: Path,
) -> None:
    existing_master = (
        archive_root
        / "master"
        / "PEARL_master_news.csv"
    )

    if not existing_master.exists():
        return

    if _same_file(
        existing_master,
        incoming_master,
    ):
        return

    now = datetime.now(CAMBODIA_TZ)
    backup_folder = (
        archive_root
        / "master_backups"
        / f"{now.year:04d}"
        / f"{now.month:02d}"
    )

    backup_folder.mkdir(
        parents=True,
        exist_ok=True,
    )

    backup_name = (
        "PEARL_master_news_"
        f"{now:%Y%m%d_%H%M%S}.csv"
    )

    shutil.copy2(
        existing_master,
        backup_folder / backup_name,
    )


def _destination_folder(
    artifact_category: str,
    run_created_at: str,
) -> Path:
    run_time = _parse_github_datetime(
        run_created_at
    )

    year = f"{run_time.year:04d}"
    month = f"{run_time.month:02d}"
    day = f"{run_time.day:02d}"

    if artifact_category == "daily":
        return Path("daily") / year / month / day

    if artifact_category == "weekly":
        iso_year, iso_week, _ = run_time.isocalendar()
        return (
            Path("weekly")
            / f"{iso_year:04d}"
            / f"W{iso_week:02d}"
        )

    if artifact_category == "monthly":
        return Path("monthly") / year / month

    if artifact_category == "qa":
        return Path("qa") / year / month / day

    if artifact_category == "raw_archive":
        return (
            Path("raw_archive")
            / year
            / month
            / day
        )

    if artifact_category == "logs":
        return Path("logs") / year / month

    if artifact_category == "master_backups":
        return (
            Path("master_backups")
            / year
            / month
        )

    if artifact_category == "monthly_zip":
        return Path("monthly_zip") / year

    if artifact_category == "master":
        return Path("master")

    return Path("sync_state") / "unclassified"


def _find_artifact_folders(
    temporary_root: Path,
) -> list[Path]:
    matches: list[Path] = []

    for candidate in temporary_root.rglob("*"):
        if not candidate.is_dir():
            continue

        if candidate.name.lower() not in RECOGNIZED_ARTIFACT_FOLDERS:
            continue

        matches.append(candidate)

    matches.sort(
        key=lambda path: len(path.parts)
    )

    selected: list[Path] = []

    for candidate in matches:
        is_nested = any(
            selected_folder in candidate.parents
            for selected_folder in selected
        )

        if not is_nested:
            selected.append(candidate)

    return selected


def _archive_downloaded_artifacts(
    temporary_root: Path,
    archive_root: Path,
    workflow_run: WorkflowRun,
) -> int:
    artifact_folders = _find_artifact_folders(
        temporary_root
    )

    if not artifact_folders:
        raise RuntimeError(
            "Artifacts downloaded, but no recognized PEARL "
            "artifact folders were found."
        )

    copied_count = 0

    for source_folder in artifact_folders:
        category = source_folder.name.lower()

        for source_file in source_folder.rglob("*"):
            if not source_file.is_file():
                continue

            relative_path = source_file.relative_to(
                source_folder
            )

            if (
                category == "master"
                and source_file.name
                == "PEARL_master_news.csv"
            ):
                _backup_existing_master(
                    archive_root,
                    source_file,
                )

                destination = (
                    archive_root
                    / "master"
                    / source_file.name
                )
            else:
                destination = (
                    archive_root
                    / _destination_folder(
                        category,
                        workflow_run.created_at,
                    )
                    / relative_path
                )

            copied = _copy_file(
                source_file,
                destination,
            )

            if copied:
                copied_count += 1

    return copied_count


def synchronize(
    *,
    repository: str,
    archive_root: Path,
    limit: int,
    latest_per_category: int,
) -> int:
    _ensure_github_cli_ready()
    _ensure_archive_tree(archive_root)

    state = _load_state(archive_root)
    recorded_runs = state.setdefault(
        "runs",
        {},
    )

    candidates = _list_candidate_runs(
        repository,
        limit,
    )

    grouped: dict[str, list[WorkflowRun]] = {
        "daily": [],
        "weekly": [],
        "monthly": [],
    }

    for run in candidates:
        grouped[run.category].append(run)

    selected_runs: list[WorkflowRun] = []

    for category in (
        "daily",
        "weekly",
        "monthly",
    ):
        selected_runs.extend(
            grouped[category][
                :latest_per_category
            ]
        )

    selected_runs.sort(
        key=lambda run: run.created_at
    )

    print("=" * 72)
    print("PEARL GitHub Artifact Synchronization v4.2")
    print(f"Repository : {repository}")
    print(f"Archive    : {archive_root}")
    print("=" * 72)

    downloaded_runs = 0
    files_copied = 0
    skipped_existing = 0
    skipped_no_artifact = 0
    errors = 0

    for workflow_run in selected_runs:
        run_key = str(workflow_run.run_id)

        if run_key in recorded_runs:
            print(
                f"[SKIP] "
                f"{workflow_run.category:<7} "
                f"run {workflow_run.run_id}: "
                "already archived"
            )
            skipped_existing += 1
            continue

        try:
            artifacts = _list_active_artifacts(
                repository,
                workflow_run.run_id,
            )

            if not artifacts:
                print(
                    f"[SKIP] "
                    f"{workflow_run.category:<7} "
                    f"run {workflow_run.run_id}: "
                    "no active artifacts"
                )
                skipped_no_artifact += 1
                continue

            print(
                f"[GET ] "
                f"{workflow_run.category:<7} "
                f"run {workflow_run.run_id}: "
                f"{len(artifacts)} artifact(s)"
            )

            with tempfile.TemporaryDirectory(
                prefix=(
                    f"PEARL-sync-"
                    f"{workflow_run.run_id}-"
                )
            ) as temporary_directory:
                temporary_root = Path(
                    temporary_directory
                )

                _download_run_artifacts(
                    repository,
                    workflow_run.run_id,
                    temporary_root,
                )

                copied = _archive_downloaded_artifacts(
                    temporary_root,
                    archive_root,
                    workflow_run,
                )

            recorded_runs[run_key] = {
                "workflow_name": (
                    workflow_run.workflow_name
                ),
                "category": (
                    workflow_run.category
                ),
                "branch": workflow_run.branch,
                "created_at": (
                    workflow_run.created_at
                ),
                "updated_at": (
                    workflow_run.updated_at
                ),
                "archived_at": datetime.now(
                    CAMBODIA_TZ
                ).isoformat(),
                "files_copied": copied,
            }

            _save_state(
                archive_root,
                state,
            )

            downloaded_runs += 1
            files_copied += copied

            print(
                f"[ OK ] "
                f"{workflow_run.category:<7} "
                f"run {workflow_run.run_id}: "
                f"{copied} file(s) archived"
            )

        except Exception as exc:
            errors += 1

            print(
                f"[ERR ] "
                f"{workflow_run.category:<7} "
                f"run {workflow_run.run_id}: "
                f"{exc}",
                file=sys.stderr,
            )

    print("-" * 72)
    print(f"Downloaded runs       : {downloaded_runs}")
    print(f"Files copied          : {files_copied}")
    print(f"Skipped already saved : {skipped_existing}")
    print(f"Skipped no artifact   : {skipped_no_artifact}")
    print(f"Errors                : {errors}")
    print("=" * 72)

    return 1 if errors else 0


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Download successful PEARL GitHub Actions "
            "artifacts into the permanent Windows archive."
        )
    )

    parser.add_argument(
        "--repo",
        default=os.getenv(
            "PEARL_GITHUB_REPOSITORY",
            DEFAULT_REPOSITORY,
        ),
        help=(
            "GitHub repository in owner/name format."
        ),
    )

    parser.add_argument(
        "--archive-root",
        default=os.getenv(
            "PEARL_ARCHIVE_ROOT",
            DEFAULT_ARCHIVE_ROOT,
        ),
        help=(
            "Permanent local archive root."
        ),
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help=(
            "Maximum number of recent completed "
            "workflow runs to inspect."
        ),
    )

    parser.add_argument(
        "--latest-per-category",
        type=int,
        default=10,
        help=(
            "Maximum number of runs to process for "
            "each of daily, weekly and monthly."
        ),
    )

    return parser.parse_args()


def main() -> int:
    arguments = _parse_arguments()

    try:
        return synchronize(
            repository=arguments.repo,
            archive_root=Path(
                arguments.archive_root
            ),
            limit=arguments.limit,
            latest_per_category=(
                arguments.latest_per_category
            ),
        )

    except KeyboardInterrupt:
        print(
            "\nSynchronization cancelled.",
            file=sys.stderr,
        )
        return 130

    except Exception as exc:
        print(
            f"FATAL: {exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())