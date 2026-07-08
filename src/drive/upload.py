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


def upload_file(local_path, filename=None):
    folder_id = os.environ["GOOGLE_DRIVE_FOLDER_ID"]
    service = get_drive_service()

    name = filename or os.path.basename(local_path)

    q = f"'{folder_id}' in parents and name='{name}' and trashed=false"
    existing = service.files().list(
        q=q,
        fields="files(id,name)",
        pageSize=100,
    ).execute().get("files", [])

    for file in existing:
        service.files().delete(fileId=file["id"]).execute()

    metadata = {
        "name": name,
        "parents": [folder_id],
    }

    media = MediaFileUpload(local_path, resumable=True)

    result = service.files().create(
        body=metadata,
        media_body=media,
        fields="id,name,webViewLink",
    ).execute()

    print(f"Uploaded: {result['name']} -> {result.get('webViewLink')}")
    return result


def download_file_by_name(filename, local_path):
    folder_id = os.environ["GOOGLE_DRIVE_FOLDER_ID"]
    service = get_drive_service()

    q = f"'{folder_id}' in parents and name='{filename}' and trashed=false"
    files = service.files().list(
        q=q,
        fields="files(id,name)",
        pageSize=10,
    ).execute().get("files", [])

    if not files:
        print(f"No existing file found in Drive: {filename}")
        return False

    file_id = files[0]["id"]

    Path(local_path).parent.mkdir(parents=True, exist_ok=True)

    request = service.files().get_media(fileId=file_id)

    with io.FileIO(local_path, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False

        while not done:
            status, done = downloader.next_chunk()

    print(f"Downloaded from Drive: {filename}")
    return True
