from __future__ import annotations

import io
import json
import os
from pathlib import Path
from typing import Any

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def get_drive_service():
    """
    Authenticate using a Google Service Account stored in the GitHub Secret
    GOOGLE_SERVICE_ACCOUNT_JSON.
    """
    service_account_json = os.environ.get(
        "GOOGLE_SERVICE_ACCOUNT_JSON", ""
    ).strip()

    if not service_account_json:
        raise RuntimeError(
            "Missing GitHub Secret: GOOGLE_SERVICE_ACCOUNT_JSON"
        )

    try:
        service_account_info = json.loads(service_account_json)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON."
        ) from exc

    creds = Credentials.from_service_account_info(
        service_account_info,
        scopes=SCOPES,
    )

    return build(
        "drive",
        "v3",
        credentials=creds,
        cache_discovery=False,
    )
