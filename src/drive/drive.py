"""Deprecated Google Drive API integration.

Version 4 deliberately does not authenticate to Google Drive from GitHub
Actions. Use GitHub Actions artifacts, the versioned normalized master CSV,
or run locally with PEARL_DATA_ROOT pointing to a Google Drive for desktop
synced folder.
"""


def _disabled(*args, **kwargs):
    raise RuntimeError(
        "Direct Google Drive API access is disabled in PEARL v4. "
        "Use GitHub artifacts or Google Drive for desktop local sync."
    )


get_drive_service = _disabled
resolve_subfolder = _disabled
upload_file = _disabled
download_file_by_id = _disabled
download_file_by_name = _disabled
copy_drive_file = _disabled
find_file_by_name = _disabled
find_files_by_name = _disabled
get_file_metadata = _disabled
