from __future__ import annotations

import io
import json
import os
from pathlib import Path
from typing import Any

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload


# Full Drive scope is required because the service account must:
# - read the existing master CSV,
# - update the master,
# - create backups,
# - upload reports into a folder shared with the service account.
SCOPES = ["https://www.googleapis.com/auth/drive"]


def _required_environment_variable(name: str) -> str:
    """
    Return a required environment variable.

    Raises a clear error when a GitHub secret or environment variable
    is missing.
    """
    value = os.getenv(name, "").strip()

    if not value:
        raise RuntimeError(
            f"Missing required environment variable or GitHub Secret: {name}"
        )

    return value


def get_drive_service():
    """
    Authenticate to Google Drive using a service account.

    The complete service-account JSON key must be stored in the GitHub
    repository secret named GOOGLE_SERVICE_ACCOUNT_JSON.
    """
    service_account_json = _required_environment_variable(
        "GOOGLE_SERVICE_ACCOUNT_JSON"
    )

    try:
        service_account_info = json.loads(service_account_json)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON. "
            "Open the downloaded service-account JSON key, copy its entire "
            "contents, and paste it into the GitHub secret."
        ) from exc

    required_json_fields = {
        "type",
        "project_id",
        "private_key",
        "client_email",
        "token_uri",
    }

    missing_fields = required_json_fields - set(service_account_info)

    if missing_fields:
        raise RuntimeError(
            "GOOGLE_SERVICE_ACCOUNT_JSON is missing required fields: "
            f"{sorted(missing_fields)}"
        )

    if service_account_info.get("type") != "service_account":
        raise RuntimeError(
            "GOOGLE_SERVICE_ACCOUNT_JSON is not a service-account key."
        )

    credentials = Credentials.from_service_account_info(
        service_account_info,
        scopes=SCOPES,
    )

    return build(
        "drive",
        "v3",
        credentials=credentials,
        cache_discovery=False,
    )


def find_files_by_name(
    filename: str,
    *,
    folder_id: str | None = None,
) -> list[dict[str, Any]]:
    """
    Find non-trashed files with an exact name inside a Google Drive folder.
    """
    target_folder_id = (
        folder_id
        or _required_environment_variable("GOOGLE_DRIVE_FOLDER_ID")
    )

    escaped_filename = filename.replace("\\", "\\\\").replace("'", "\\'")

    service = get_drive_service()

    try:
        response = (
            service.files()
            .list(
                q=(
                    f"'{target_folder_id}' in parents "
                    f"and name='{escaped_filename}' "
                    "and trashed=false"
                ),
                fields=(
                    "files("
                    "id,"
                    "name,"
                    "webViewLink,"
                    "modifiedTime,"
                    "size,"
                    "mimeType,"
                    "parents"
                    ")"
                ),
                orderBy="modifiedTime desc",
                pageSize=100,
                spaces="drive",
            )
            .execute()
        )
    except HttpError as exc:
        raise RuntimeError(
            f"Google Drive search failed for file {filename!r}: {exc}"
        ) from exc

    return response.get("files", [])


def find_file_by_name(
    filename: str,
    *,
    require_unique: bool = False,
    folder_id: str | None = None,
) -> dict[str, Any] | None:
    """
    Return the most recently modified matching file.

    When require_unique=True, raise an error if duplicate filenames exist.
    """
    files = find_files_by_name(
        filename,
        folder_id=folder_id,
    )

    if require_unique and len(files) > 1:
        ids = ", ".join(item["id"] for item in files)

        raise RuntimeError(
            f"Multiple Google Drive files named {filename!r} were found: "
            f"{ids}. Keep only one active production master or configure "
            "GOOGLE_MASTER_FILE_ID with the correct file ID."
        )

    return files[0] if files else None


def get_file_metadata(file_id: str) -> dict[str, Any]:
    """
    Get metadata for one Google Drive file.
    """
    if not file_id or not file_id.strip():
        raise ValueError("Google Drive file ID cannot be empty.")

    try:
        return (
            get_drive_service()
            .files()
            .get(
                fileId=file_id.strip(),
                fields=(
                    "id,"
                    "name,"
                    "webViewLink,"
                    "modifiedTime,"
                    "size,"
                    "mimeType,"
                    "parents"
                ),
            )
            .execute()
        )
    except HttpError as exc:
        raise RuntimeError(
            f"Unable to access Google Drive file ID {file_id!r}. "
            "Confirm that the ID is correct and that the file or its parent "
            "folder is shared with the service account as Editor."
        ) from exc


def download_file_by_id(
    file_id: str,
    local_path: str,
) -> dict[str, Any]:
    """
    Download a normal binary file from Google Drive by file ID.
    """
    service = get_drive_service()
    metadata = get_file_metadata(file_id)

    mime_type = metadata.get("mimeType", "")

    if mime_type.startswith("application/vnd.google-apps."):
        raise RuntimeError(
            f"{metadata.get('name', file_id)!r} is a native Google file "
            f"with MIME type {mime_type!r}. The production master must remain "
            "an actual CSV file, not a converted Google Sheet."
        )

    destination = Path(local_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    try:
        request = service.files().get_media(fileId=file_id)

        with io.FileIO(destination, "wb") as file_handle:
            downloader = MediaIoBaseDownload(file_handle, request)
            done = False

            while not done:
                _, done = downloader.next_chunk()

    except HttpError as exc:
        raise RuntimeError(
            f"Failed to download Google Drive file "
            f"{metadata.get('name', file_id)!r}: {exc}"
        ) from exc

    if not destination.exists() or destination.stat().st_size == 0:
        raise RuntimeError(
            f"Downloaded file {metadata.get('name', file_id)!r} is empty."
        )

    print(
        f"Downloaded from Drive: "
        f"{metadata['name']} [{metadata['id']}]"
    )

    return metadata


def download_file_by_name(
    filename: str,
    local_path: str,
    *,
    require_unique: bool = False,
    folder_id: str | None = None,
) -> bool:
    """
    Find and download a file by its exact name.
    """
    existing = find_file_by_name(
        filename,
        require_unique=require_unique,
        folder_id=folder_id,
    )

    if not existing:
        print(f"No file found in Drive: {filename}")
        return False

    download_file_by_id(
        existing["id"],
        local_path,
    )

    return True


def upload_file(
    local_path: str,
    filename: str | None = None,
    *,
    replace: bool = True,
    file_id: str | None = None,
    require_unique: bool = False,
    folder_id: str | None = None,
) -> dict[str, Any]:
    """
    Upload or update a file in Google Drive.

    Behavior:
    - file_id supplied + replace=True:
      update that exact file.
    - no file_id + replace=True:
      search for the same filename and update it when found.
    - replace=False:
      always create a new file.
    """
    source_path = Path(local_path)

    if not source_path.exists():
        raise FileNotFoundError(
            f"Upload source file does not exist: {source_path}"
        )

    if not source_path.is_file():
        raise RuntimeError(
            f"Upload source path is not a file: {source_path}"
        )

    if source_path.stat().st_size == 0:
        raise RuntimeError(
            f"Refusing to upload an empty file: {source_path}"
        )

    target_folder_id = (
        folder_id
        or _required_environment_variable("GOOGLE_DRIVE_FOLDER_ID")
    )

    service = get_drive_service()
    drive_name = filename or source_path.name

    media = MediaFileUpload(
        str(source_path),
        resumable=True,
    )

    target: dict[str, Any] | None = None

    if file_id:
        target = get_file_metadata(file_id)

    elif replace:
        target = find_file_by_name(
            drive_name,
            require_unique=require_unique,
            folder_id=target_folder_id,
        )

    try:
        if target and replace:
            result = (
                service.files()
                .update(
                    fileId=target["id"],
                    body={"name": drive_name},
                    media_body=media,
                    fields=(
                        "id,"
                        "name,"
                        "webViewLink,"
                        "modifiedTime,"
                        "size,"
                        "mimeType,"
                        "parents"
                    ),
                )
                .execute()
            )

            print(
                f"Updated existing file: "
                f"{drive_name} [{result['id']}]"
            )

            return result

        result = (
            service.files()
            .create(
                body={
                    "name": drive_name,
                    "parents": [target_folder_id],
                },
                media_body=media,
                fields=(
                    "id,"
                    "name,"
                    "webViewLink,"
                    "modifiedTime,"
                    "size,"
                    "mimeType,"
                    "parents"
                ),
            )
            .execute()
        )

        print(
            f"Uploaded new file: "
            f"{drive_name} [{result['id']}]"
        )

        return result

    except HttpError as exc:
        raise RuntimeError(
            f"Failed to upload {drive_name!r} to Google Drive: {exc}"
        ) from exc


def copy_drive_file(
    file_id: str,
    new_name: str,
    *,
    folder_id: str | None = None,
) -> dict[str, Any]:
    """
    Create a copy of an existing Google Drive file.

    This is used for pre-update master backups.
    """
    target_folder_id = (
        folder_id
        or _required_environment_variable("GOOGLE_DRIVE_FOLDER_ID")
    )

    # Validate that the source is accessible before copying it.
    source_metadata = get_file_metadata(file_id)

    try:
        result = (
            get_drive_service()
            .files()
            .copy(
                fileId=file_id,
                body={
                    "name": new_name,
                    "parents": [target_folder_id],
                },
                fields=(
                    "id,"
                    "name,"
                    "webViewLink,"
                    "modifiedTime,"
                    "size,"
                    "mimeType,"
                    "parents"
                ),
            )
            .execute()
        )

    except HttpError as exc:
        raise RuntimeError(
            f"Failed to create backup of "
            f"{source_metadata.get('name', file_id)!r}: {exc}"
        ) from exc

    print(
        f"Created Drive backup: "
        f"{new_name} [{result['id']}]"
    )

    return result
