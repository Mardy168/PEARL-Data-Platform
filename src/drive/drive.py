from __future__ import annotations

import io
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload


SCOPES = ["https://www.googleapis.com/auth/drive"]
FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"

FILE_FIELDS = (
    "id,name,webViewLink,modifiedTime,size,mimeType,parents,owners"
)


def _required_env(name: str) -> str:
    """
    Return a required environment variable.

    Raises:
        RuntimeError: If the variable is missing or empty.
    """
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(
            f"Missing required GitHub Secret/environment variable: {name}"
        )
    return value


@lru_cache(maxsize=1)
def get_drive_service():
    """
    Build and cache a Google Drive API service using OAuth credentials.

    Required GitHub secrets:
        GOOGLE_CLIENT_ID
        GOOGLE_CLIENT_SECRET
        GOOGLE_REFRESH_TOKEN

    This authenticates as the dedicated PEARL Google user, allowing
    GitHub Actions to create, update, copy and delete files in that
    user's consumer Google Drive.
    """
    client_id = _required_env("GOOGLE_CLIENT_ID")
    client_secret = _required_env("GOOGLE_CLIENT_SECRET")
    refresh_token = _required_env("GOOGLE_REFRESH_TOKEN")

    credentials = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
    )

    try:
        return build(
            "drive",
            "v3",
            credentials=credentials,
            cache_discovery=False,
        )
    except Exception as exc:
        raise RuntimeError(
            "Failed to initialize the Google Drive API service. "
            "Check GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET and "
            "GOOGLE_REFRESH_TOKEN."
        ) from exc


def _escape_query_value(value: str) -> str:
    """
    Escape a string for use in a Google Drive search query.
    """
    return str(value).replace("\\", "\\\\").replace("'", "\\'")


def get_file_metadata(file_id: str) -> dict[str, Any]:
    """
    Retrieve metadata for a Google Drive file.

    Args:
        file_id: Google Drive file ID.

    Returns:
        File metadata dictionary.
    """
    clean_id = str(file_id).strip()

    if not clean_id:
        raise ValueError("Google Drive file ID cannot be empty.")

    try:
        return (
            get_drive_service()
            .files()
            .get(
                fileId=clean_id,
                fields=FILE_FIELDS,
                supportsAllDrives=True,
            )
            .execute()
        )
    except HttpError as exc:
        raise RuntimeError(
            f"Cannot access Google Drive file ID {clean_id!r}. "
            "Confirm that the ID is correct and that the OAuth user "
            "has access to the file."
        ) from exc


def list_children(
    folder_id: str,
    *,
    name: str | None = None,
    mime_type: str | None = None,
    page_size: int = 100,
) -> list[dict[str, Any]]:
    """
    List files directly inside a Google Drive folder.

    Args:
        folder_id: Parent folder ID.
        name: Optional exact filename filter.
        mime_type: Optional MIME type filter.
        page_size: Maximum items per API page.

    Returns:
        List of file metadata dictionaries.
    """
    clean_folder_id = str(folder_id).strip()

    if not clean_folder_id:
        raise ValueError("Google Drive folder ID cannot be empty.")

    query_parts = [
        f"'{clean_folder_id}' in parents",
        "trashed=false",
    ]

    if name is not None:
        query_parts.append(
            f"name='{_escape_query_value(name)}'"
        )

    if mime_type is not None:
        query_parts.append(
            f"mimeType='{_escape_query_value(mime_type)}'"
        )

    files: list[dict[str, Any]] = []
    page_token: str | None = None

    try:
        while True:
            response = (
                get_drive_service()
                .files()
                .list(
                    q=" and ".join(query_parts),
                    fields=f"nextPageToken,files({FILE_FIELDS})",
                    orderBy="modifiedTime desc",
                    pageSize=page_size,
                    spaces="drive",
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                    pageToken=page_token,
                )
                .execute()
            )

            files.extend(response.get("files", []))
            page_token = response.get("nextPageToken")

            if not page_token:
                break

    except HttpError as exc:
        raise RuntimeError(
            f"Google Drive listing failed for folder "
            f"{clean_folder_id!r}: {exc}"
        ) from exc

    return files


def find_files_by_name(
    filename: str,
    *,
    folder_id: str | None = None,
) -> list[dict[str, Any]]:
    """
    Find all files with an exact name inside a folder.
    """
    target_folder = (
        folder_id
        or _required_env("GOOGLE_DRIVE_FOLDER_ID")
    )

    return list_children(
        target_folder,
        name=filename,
    )


def find_file_by_name(
    filename: str,
    *,
    require_unique: bool = False,
    folder_id: str | None = None,
) -> dict[str, Any] | None:
    """
    Find one file by exact name.

    Args:
        filename: Exact filename.
        require_unique: Raise an error if duplicates exist.
        folder_id: Optional folder ID.

    Returns:
        Most recently modified matching file, or None.
    """
    files = find_files_by_name(
        filename,
        folder_id=folder_id,
    )

    if require_unique and len(files) > 1:
        ids = ", ".join(
            item["id"] for item in files
        )
        raise RuntimeError(
            f"Multiple files named {filename!r} were found: {ids}"
        )

    return files[0] if files else None


@lru_cache(maxsize=32)
def resolve_subfolder(
    folder_name: str,
    parent_folder_id: str | None = None,
) -> str:
    """
    Resolve the ID of an existing child folder.

    The workflow intentionally does not create folders silently.
    """
    parent_id = (
        parent_folder_id
        or _required_env("GOOGLE_DRIVE_FOLDER_ID")
    )

    matches = list_children(
        parent_id,
        name=folder_name,
        mime_type=FOLDER_MIME_TYPE,
    )

    if not matches:
        raise RuntimeError(
            f"Required Google Drive subfolder {folder_name!r} "
            "was not found under the configured main folder."
        )

    if len(matches) > 1:
        ids = ", ".join(
            item["id"] for item in matches
        )
        raise RuntimeError(
            f"Multiple Google Drive subfolders named "
            f"{folder_name!r} were found: {ids}"
        )

    return matches[0]["id"]


def download_file_by_id(
    file_id: str,
    local_path: str,
) -> dict[str, Any]:
    """
    Download a non-native Google Drive file by ID.

    Native Google Docs, Sheets and Slides are rejected because
    they must be exported rather than downloaded with get_media().
    """
    service = get_drive_service()
    metadata = get_file_metadata(file_id)

    mime_type = metadata.get("mimeType", "")

    if mime_type.startswith(
        "application/vnd.google-apps."
    ):
        raise RuntimeError(
            f"{metadata.get('name', file_id)!r} is a native "
            "Google file. The production master must remain "
            "a real CSV file, not a Google Sheet."
        )

    destination = Path(local_path)
    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        request = service.files().get_media(
            fileId=file_id,
            supportsAllDrives=True,
        )

        with io.FileIO(destination, "wb") as file_handle:
            downloader = MediaIoBaseDownload(
                file_handle,
                request,
            )

            done = False
            while not done:
                _, done = downloader.next_chunk()

    except HttpError as exc:
        raise RuntimeError(
            f"Failed to download "
            f"{metadata.get('name', file_id)!r}: {exc}"
        ) from exc

    if (
        not destination.exists()
        or destination.stat().st_size == 0
    ):
        raise RuntimeError(
            f"Downloaded file "
            f"{metadata.get('name', file_id)!r} is empty."
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
    Download a file by exact name.

    Returns:
        True when downloaded, False when no file is found.
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
    Upload or replace a file in Google Drive.

    Args:
        local_path: Local source file.
        filename: Optional destination filename.
        replace: Replace an existing file when found.
        file_id: Explicit Drive file ID to replace.
        require_unique: Reject duplicate destination names.
        folder_id: Destination folder ID.

    Returns:
        Uploaded or updated Drive metadata.
    """
    source = Path(local_path)

    if not source.is_file():
        raise FileNotFoundError(
            f"Upload source file does not exist: {source}"
        )

    if source.stat().st_size == 0:
        raise RuntimeError(
            f"Refusing to upload empty file: {source}"
        )

    target_folder = (
        folder_id
        or _required_env("GOOGLE_DRIVE_FOLDER_ID")
    )

    destination_name = filename or source.name
    service = get_drive_service()

    media = MediaFileUpload(
        str(source),
        resumable=True,
    )

    target: dict[str, Any] | None = None

    if file_id:
        target = get_file_metadata(file_id)
    elif replace:
        target = find_file_by_name(
            destination_name,
            require_unique=require_unique,
            folder_id=target_folder,
        )

    try:
        if target and replace:
            result = (
                service.files()
                .update(
                    fileId=target["id"],
                    body={
                        "name": destination_name
                    },
                    media_body=media,
                    fields=FILE_FIELDS,
                    supportsAllDrives=True,
                )
                .execute()
            )

            print(
                f"Updated existing file: "
                f"{destination_name} [{result['id']}]"
            )

            return result

        result = (
            service.files()
            .create(
                body={
                    "name": destination_name,
                    "parents": [target_folder],
                },
                media_body=media,
                fields=FILE_FIELDS,
                supportsAllDrives=True,
            )
            .execute()
        )

        print(
            f"Uploaded new file: "
            f"{destination_name} [{result['id']}]"
        )

        return result

    except HttpError as exc:
        raise RuntimeError(
            f"Failed to upload {destination_name!r}. "
            "Confirm that the OAuth user owns or can edit the "
            "destination folder and has available Drive storage. "
            f"Details: {exc}"
        ) from exc


def copy_drive_file(
    file_id: str,
    new_name: str,
    *,
    folder_id: str | None = None,
) -> dict[str, Any]:
    """
    Copy a Drive file into a destination folder.

    Used for production master backups.
    """
    target_folder = (
        folder_id
        or _required_env("GOOGLE_DRIVE_FOLDER_ID")
    )

    source = get_file_metadata(file_id)

    try:
        result = (
            get_drive_service()
            .files()
            .copy(
                fileId=file_id,
                body={
                    "name": new_name,
                    "parents": [target_folder],
                },
                fields=FILE_FIELDS,
                supportsAllDrives=True,
            )
            .execute()
        )

    except HttpError as exc:
        raise RuntimeError(
            f"Failed to create backup of "
            f"{source.get('name', file_id)!r}. "
            "Confirm that the OAuth user has permission and "
            "available Drive storage. "
            f"Details: {exc}"
        ) from exc

    print(
        f"Created Drive backup: "
        f"{new_name} [{result['id']}]"
    )

    return result


def move_drive_file(
    file_id: str,
    destination_folder_id: str,
) -> dict[str, Any]:
    """
    Move an existing Drive file to another folder.

    The file remains the same Drive object and keeps its file ID.
    """
    metadata = get_file_metadata(file_id)

    current_parents = metadata.get("parents", [])
    remove_parents = ",".join(current_parents)

    try:
        result = (
            get_drive_service()
            .files()
            .update(
                fileId=file_id,
                addParents=destination_folder_id,
                removeParents=remove_parents or None,
                fields=FILE_FIELDS,
                supportsAllDrives=True,
            )
            .execute()
        )

    except HttpError as exc:
        raise RuntimeError(
            f"Failed to move Drive file "
            f"{metadata.get('name', file_id)!r}: {exc}"
        ) from exc

    print(
        f"Moved Drive file: "
        f"{result['name']} [{result['id']}]"
    )

    return result


def delete_drive_file(file_id: str) -> None:
    """
    Permanently delete a Google Drive file.

    Use carefully. This is primarily intended for cleanup tools,
    not normal daily production runs.
    """
    metadata = get_file_metadata(file_id)

    try:
        (
            get_drive_service()
            .files()
            .delete(
                fileId=file_id,
                supportsAllDrives=True,
            )
            .execute()
        )

    except HttpError as exc:
        raise RuntimeError(
            f"Failed to delete Drive file "
            f"{metadata.get('name', file_id)!r}: {exc}"
        ) from exc

    print(
        f"Deleted Drive file: "
        f"{metadata.get('name', file_id)} [{file_id}]"
    )


def verify_drive_access() -> dict[str, Any]:
    """
    Verify authentication and access to the configured Drive structure.

    Returns:
        A dictionary containing the main folder, master file and
        resolved production subfolders.
    """
    main_folder_id = _required_env(
        "GOOGLE_DRIVE_FOLDER_ID"
    )
    master_file_id = _required_env(
        "GOOGLE_MASTER_FILE_ID"
    )

    main_folder = get_file_metadata(
        main_folder_id
    )
    master_file = get_file_metadata(
        master_file_id
    )

    required_subfolders = [
        "Daily",
        "Weekly",
        "Monthly",
        "Logs",
        "Master",
        "Master_Backups",
        "QA",
        "Raw_Archive",
    ]

    resolved_subfolders = {
        folder_name: resolve_subfolder(
            folder_name,
            main_folder_id,
        )
        for folder_name in required_subfolders
    }

    result = {
        "main_folder": main_folder,
        "master_file": master_file,
        "subfolders": resolved_subfolders,
    }

    print("Google Drive access verification passed.")
    print(
        f"Main folder: "
        f"{main_folder.get('name')} "
        f"[{main_folder.get('id')}]"
    )
    print(
        f"Master file: "
        f"{master_file.get('name')} "
        f"[{master_file.get('id')}]"
    )

    for folder_name, folder_id in (
        resolved_subfolders.items()
    ):
        print(
            f"Subfolder: "
            f"{folder_name} [{folder_id}]"
        )

    return result
