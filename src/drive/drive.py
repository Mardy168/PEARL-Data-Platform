from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def get_drive_service():
    creds = Credentials(
        token=None,
        refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        scopes=SCOPES,
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def find_files_by_name(filename: str) -> list[dict[str, Any]]:
    folder_id = os.environ["GOOGLE_DRIVE_FOLDER_ID"]
    escaped = filename.replace("'", "\\'")
    service = get_drive_service()
    response = service.files().list(
        q=f"'{folder_id}' in parents and name='{escaped}' and trashed=false",
        fields="files(id,name,webViewLink,modifiedTime,size,mimeType,parents)",
        orderBy="modifiedTime desc",
        pageSize=100,
    ).execute()
    return response.get("files", [])


def find_file_by_name(filename: str, *, require_unique: bool = False):
    files = find_files_by_name(filename)
    if require_unique and len(files) > 1:
        ids = ", ".join(item["id"] for item in files)
        raise RuntimeError(
            f"Multiple Google Drive files named {filename!r} were found ({ids}). "
            "Keep only one active production master or configure GOOGLE_MASTER_FILE_ID."
        )
    return files[0] if files else None


def get_file_metadata(file_id: str) -> dict[str, Any]:
    return get_drive_service().files().get(
        fileId=file_id,
        fields="id,name,webViewLink,modifiedTime,size,mimeType,parents",
    ).execute()


def download_file_by_id(file_id: str, local_path: str) -> dict[str, Any]:
    service = get_drive_service()
    metadata = get_file_metadata(file_id)
    Path(local_path).parent.mkdir(parents=True, exist_ok=True)
    request = service.files().get_media(fileId=file_id)
    with io.FileIO(local_path, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
    print(f"Downloaded from Drive: {metadata['name']} [{file_id}]")
    return metadata


def download_file_by_name(filename: str, local_path: str, *, require_unique: bool = False):
    existing = find_file_by_name(filename, require_unique=require_unique)
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
):
    folder_id = os.environ["GOOGLE_DRIVE_FOLDER_ID"]
    service = get_drive_service()
    name = filename or os.path.basename(local_path)
    media = MediaFileUpload(local_path, resumable=True)

    target = None
    if file_id:
        target = get_file_metadata(file_id)
    elif replace:
        target = find_file_by_name(name, require_unique=require_unique)

    if target and replace:
        result = service.files().update(
            fileId=target["id"],
            body={"name": name},
            media_body=media,
            fields="id,name,webViewLink,modifiedTime,size",
        ).execute()
        print(f"Updated existing file: {name} [{target['id']}]")
        return result

    result = service.files().create(
        body={"name": name, "parents": [folder_id]},
        media_body=media,
        fields="id,name,webViewLink,modifiedTime,size",
    ).execute()
    print(f"Uploaded new file: {name} [{result['id']}]")
    return result


def copy_drive_file(file_id: str, new_name: str) -> dict[str, Any]:
    folder_id = os.environ["GOOGLE_DRIVE_FOLDER_ID"]
    result = get_drive_service().files().copy(
        fileId=file_id,
        body={"name": new_name, "parents": [folder_id]},
        fields="id,name,webViewLink,modifiedTime,size",
    ).execute()
    print(f"Created Drive backup: {new_name} [{result['id']}]")
    return result
