from __future__ import annotations

import io
import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

SCOPES = ["https://www.googleapis.com/auth/drive"]
FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required GitHub Secret/environment variable: {name}")
    return value


@lru_cache(maxsize=1)
def get_drive_service():
    """Build a cached Google Drive service using a service-account JSON key."""
    raw = _required_env("GOOGLE_SERVICE_ACCOUNT_JSON")
    try:
        info = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON.") from exc

    required = {"type", "project_id", "private_key", "client_email", "token_uri"}
    missing = required - set(info)
    if missing:
        raise RuntimeError(f"Service-account JSON is missing fields: {sorted(missing)}")
    if info.get("type") != "service_account":
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON is not a service-account key.")

    creds = ServiceAccountCredentials.from_service_account_info(info, scopes=SCOPES)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _escape_query_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def get_file_metadata(file_id: str) -> dict[str, Any]:
    if not str(file_id).strip():
        raise ValueError("Google Drive file ID cannot be empty.")
    try:
        return (
            get_drive_service()
            .files()
            .get(
                fileId=str(file_id).strip(),
                fields="id,name,webViewLink,modifiedTime,size,mimeType,parents",
                supportsAllDrives=True,
            )
            .execute()
        )
    except HttpError as exc:
        raise RuntimeError(
            f"Cannot access Google Drive file ID {file_id!r}. Confirm the ID and share access with the service account."
        ) from exc


def list_children(folder_id: str, *, name: str | None = None, mime_type: str | None = None) -> list[dict[str, Any]]:
    parts = [f"'{folder_id}' in parents", "trashed=false"]
    if name is not None:
        parts.append(f"name='{_escape_query_value(name)}'")
    if mime_type is not None:
        parts.append(f"mimeType='{_escape_query_value(mime_type)}'")
    try:
        response = (
            get_drive_service()
            .files()
            .list(
                q=" and ".join(parts),
                fields="files(id,name,webViewLink,modifiedTime,size,mimeType,parents)",
                orderBy="modifiedTime desc",
                pageSize=100,
                spaces="drive",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )
            .execute()
        )
    except HttpError as exc:
        raise RuntimeError(f"Google Drive listing failed for folder {folder_id!r}: {exc}") from exc
    return response.get("files", [])


def find_files_by_name(filename: str, *, folder_id: str | None = None) -> list[dict[str, Any]]:
    return list_children(folder_id or _required_env("GOOGLE_DRIVE_FOLDER_ID"), name=filename)


def find_file_by_name(
    filename: str,
    *,
    require_unique: bool = False,
    folder_id: str | None = None,
) -> dict[str, Any] | None:
    files = find_files_by_name(filename, folder_id=folder_id)
    if require_unique and len(files) > 1:
        ids = ", ".join(item["id"] for item in files)
        raise RuntimeError(f"Multiple files named {filename!r} were found: {ids}")
    return files[0] if files else None


@lru_cache(maxsize=32)
def resolve_subfolder(folder_name: str, parent_folder_id: str | None = None) -> str:
    """Return an existing child folder ID. The workflow never silently creates folders."""
    parent = parent_folder_id or _required_env("GOOGLE_DRIVE_FOLDER_ID")
    matches = list_children(parent, name=folder_name, mime_type=FOLDER_MIME_TYPE)
    if not matches:
        raise RuntimeError(
            f"Required Drive subfolder {folder_name!r} was not found under the configured main folder."
        )
    if len(matches) > 1:
        ids = ", ".join(item["id"] for item in matches)
        raise RuntimeError(f"Multiple Drive subfolders named {folder_name!r} were found: {ids}")
    return matches[0]["id"]


def download_file_by_id(file_id: str, local_path: str) -> dict[str, Any]:
    service = get_drive_service()
    metadata = get_file_metadata(file_id)
    mime_type = metadata.get("mimeType", "")
    if mime_type.startswith("application/vnd.google-apps."):
        raise RuntimeError(
            f"{metadata.get('name', file_id)!r} is a native Google file. The master must remain a real CSV file."
        )

    destination = Path(local_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
        with io.FileIO(destination, "wb") as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
    except HttpError as exc:
        raise RuntimeError(f"Failed to download {metadata.get('name', file_id)!r}: {exc}") from exc

    if not destination.exists() or destination.stat().st_size == 0:
        raise RuntimeError(f"Downloaded file {metadata.get('name', file_id)!r} is empty.")
    print(f"Downloaded from Drive: {metadata['name']} [{metadata['id']}]")
    return metadata


def download_file_by_name(
    filename: str,
    local_path: str,
    *,
    require_unique: bool = False,
    folder_id: str | None = None,
) -> bool:
    existing = find_file_by_name(filename, require_unique=require_unique, folder_id=folder_id)
    if not existing:
        print(f"No file found in Drive: {filename}")
        return False
    download_file_by_id(existing["id"], local_path)
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
    source = Path(local_path)
    if not source.is_file():
        raise FileNotFoundError(f"Upload source file does not exist: {source}")
    if source.stat().st_size == 0:
        raise RuntimeError(f"Refusing to upload empty file: {source}")

    target_folder = folder_id or _required_env("GOOGLE_DRIVE_FOLDER_ID")
    name = filename or source.name
    service = get_drive_service()
    media = MediaFileUpload(str(source), resumable=True)

    target = get_file_metadata(file_id) if file_id else None
    if target is None and replace:
        target = find_file_by_name(name, require_unique=require_unique, folder_id=target_folder)

    try:
        if target and replace:
            result = (
                service.files()
                .update(
                    fileId=target["id"],
                    body={"name": name},
                    media_body=media,
                    fields="id,name,webViewLink,modifiedTime,size,mimeType,parents",
                    supportsAllDrives=True,
                )
                .execute()
            )
            print(f"Updated existing file: {name} [{result['id']}]")
            return result

        result = (
            service.files()
            .create(
                body={"name": name, "parents": [target_folder]},
                media_body=media,
                fields="id,name,webViewLink,modifiedTime,size,mimeType,parents",
                supportsAllDrives=True,
            )
            .execute()
        )
        print(f"Uploaded new file: {name} [{result['id']}]")
        return result
    except HttpError as exc:
        raise RuntimeError(
            f"Failed to upload {name!r}. If this is a consumer My Drive, service-account storage limits may require OAuth or a Workspace Shared Drive. Details: {exc}"
        ) from exc


def copy_drive_file(file_id: str, new_name: str, *, folder_id: str | None = None) -> dict[str, Any]:
    target_folder = folder_id or _required_env("GOOGLE_DRIVE_FOLDER_ID")
    source = get_file_metadata(file_id)
    try:
        result = (
            get_drive_service()
            .files()
            .copy(
                fileId=file_id,
                body={"name": new_name, "parents": [target_folder]},
                fields="id,name,webViewLink,modifiedTime,size,mimeType,parents",
                supportsAllDrives=True,
            )
            .execute()
        )
    except HttpError as exc:
        raise RuntimeError(f"Failed to create backup of {source.get('name', file_id)!r}: {exc}") from exc
    print(f"Created Drive backup: {new_name} [{result['id']}]")
    return result
