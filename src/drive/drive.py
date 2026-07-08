import io
import os
from pathlib import Path

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
    return build("drive", "v3", credentials=creds)


def find_file_by_name(filename):
    folder_id = os.environ["GOOGLE_DRIVE_FOLDER_ID"]
    service = get_drive_service()

    q = f"'{folder_id}' in parents and name='{filename}' and trashed=false"

    result = service.files().list(
        q=q,
        fields="files(id,name,webViewLink,modifiedTime)",
        pageSize=10,
    ).execute()

    files = result.get("files", [])
    return files[0] if files else None


def upload_file(local_path, filename=None, replace=True):
    folder_id = os.environ["GOOGLE_DRIVE_FOLDER_ID"]
    service = get_drive_service()

    name = filename or os.path.basename(local_path)
    existing = find_file_by_name(name)

    media = MediaFileUpload(local_path, resumable=True)

    if existing and replace:
        result = service.files().update(
            fileId=existing["id"],
            media_body=media,
            fields="id,name,webViewLink,modifiedTime",
        ).execute()
        print(f"Updated existing file: {name}")
        return result

    metadata = {
        "name": name,
        "parents": [folder_id],
    }

    result = service.files().create(
        body=metadata,
        media_body=media,
        fields="id,name,webViewLink,modifiedTime",
    ).execute()

    print(f"Uploaded new file: {name}")
    return result


def download_file_by_name(filename, local_path):
    service = get_drive_service()
    existing = find_file_by_name(filename)

    if not existing:
        print(f"No file found in Drive: {filename}")
        return False

    Path(local_path).parent.mkdir(parents=True, exist_ok=True)

    request = service.files().get_media(fileId=existing["id"])

    with io.FileIO(local_path, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False

        while not done:
            _, done = downloader.next_chunk()

    print(f"Downloaded from Drive: {filename}")
    return True
