import io
import json
import os
from pathlib import Path
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def get_drive_service():
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not raw:
        raise RuntimeError("Missing GOOGLE_SERVICE_ACCOUNT_JSON secret")
    info = json.loads(raw)
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return build("drive", "v3", credentials=creds)


def upload_file(local_path, filename=None, folder_id=None):
    folder_id = folder_id or os.environ.get("GOOGLE_DRIVE_FOLDER_ID")
    if not folder_id:
        raise RuntimeError("Missing GOOGLE_DRIVE_FOLDER_ID secret")
    service = get_drive_service()
    filename = filename or os.path.basename(local_path)
    metadata = {"name": filename, "parents": [folder_id]}
    media = MediaFileUpload(local_path, resumable=True)
    result = service.files().create(body=metadata, media_body=media, fields="id, name, webViewLink").execute()
    print(f"Uploaded: {filename} -> {result.get('webViewLink')}")
    return result


def list_files(prefix="PEARL_daily_news_", folder_id=None, max_results=100):
    folder_id = folder_id or os.environ.get("GOOGLE_DRIVE_FOLDER_ID")
    service = get_drive_service()
    q = f"'{folder_id}' in parents and trashed=false and name contains '{prefix}'"
    result = service.files().list(q=q, fields="files(id,name,createdTime,modifiedTime,webViewLink)", pageSize=max_results, orderBy="createdTime desc").execute()
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
