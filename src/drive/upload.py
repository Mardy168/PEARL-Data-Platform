import io
import os
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload


SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def get_drive_service():
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    refresh_token = os.environ.get("GOOGLE_REFRESH_TOKEN")

    if not client_id or not client_secret or not refresh_token:
        raise RuntimeError(
            "Missing OAuth secrets: GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN"
        )

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
    )

    return build("drive", "v3", credentials=creds)


def upload_file(local_path, filename=None, folder_id=None):
    folder_id = folder_id or os.environ.get("GOOGLE_DRIVE_FOLDER_ID")

    if not folder_id:
        raise RuntimeError("Missing GOOGLE_DRIVE_FOLDER_ID secret")

    service = get_drive_service()
    filename = filename or os.path.basename(local_path)

    metadata = {
        "name": filename,
        "parents": [folder_id],
    }

    media = MediaFileUpload(local_path, resumable=True)

    result = service.files().create(
        body=metadata,
        media_body=media,
        fields="id, name, webViewLink",
    ).execute()

    print(f"Uploaded: {filename} -> {result.get('webViewLink')}")
    return result


def list_files(prefix="PEARL", folder_id=None, max_results=100):
    folder_id = folder_id or os.environ.get("GOOGLE_DRIVE_FOLDER_ID")

    if not folder_id:
        raise RuntimeError("Missing GOOGLE_DRIVE_FOLDER_ID secret")

    service = get_drive_service()

    q = f"'{folder_id}' in parents and trashed=false and name contains '{prefix}'"

    result = service.files().list(
        q=q,
        fields="files(id,name,createdTime,modifiedTime,webViewLink)",
        pageSize=max_results,
        orderBy="createdTime desc",
    ).execute()

    return result.get("files", [])


def download_file(file_id, local_path):
    service = get_drive_service()
    request = service.files().get_media(fileId=file_id)

    Path(local_path).parent.mkdir(parents=True, exist_ok=True)

    fh = io.FileIO(local_path, "wb")
    downloader = MediaIoBaseDownload(fh, request)

    done = False
    while not done:
        status, done = downloader.next_chunk()

    return local_path
