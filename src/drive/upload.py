import os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

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

    metadata = {
        "name": filename or os.path.basename(local_path),
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
