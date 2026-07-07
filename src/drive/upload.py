import json
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

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
    result = service.files().create(body=metadata, media_body=media, fields="id, webViewLink").execute()
    print(f"Uploaded: {filename} -> {result.get('webViewLink')}")
    return result
