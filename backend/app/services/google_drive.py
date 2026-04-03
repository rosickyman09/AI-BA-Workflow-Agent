"""
Google Drive upload service.

Supports two authentication methods (tried in order):

  1. OAuth2 with refresh token  — works with personal Google accounts (My Drive)
     Required env vars: GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN

  2. Service account JSON       — works ONLY with Shared Drives / Google Workspace
     Required env vars: GOOGLE_DRIVE_CREDENTIALS_JSON  (or GOOGLE_DRIVE_CREDENTIALS_PATH)

NOTE: Service accounts cannot upload to personal My Drive (storageQuotaExceeded).
      Use OAuth2 credentials for personal Google Drive uploads.

Both methods require: GOOGLE_DRIVE_FOLDER_ID — the root target folder ID in Drive.
Files are uploaded to per-project subfolders when available.
"""
import io
import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_CREDENTIALS_JSON: str = os.environ.get("GOOGLE_DRIVE_CREDENTIALS_JSON", "")
_CREDENTIALS_PATH: str = os.environ.get("GOOGLE_DRIVE_CREDENTIALS_PATH", "")
_FOLDER_ID: str = os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "")

# OAuth2 credentials for personal Google account uploads
_CLIENT_ID: str = os.environ.get("GOOGLE_CLIENT_ID", "")
_CLIENT_SECRET: str = os.environ.get("GOOGLE_CLIENT_SECRET", "")
_REFRESH_TOKEN: str = os.environ.get("GOOGLE_REFRESH_TOKEN", "")

# Drive scope — full access needed for accessing folders created by other auth methods
_SCOPES = ["https://www.googleapis.com/auth/drive"]

# Cached root folder IDs (populated on first use; reset on container restart)
_PENDING_FOLDER_ID: Optional[str] = None
_APPROVED_FOLDER_ID: Optional[str] = None
_URS_TEMPLATES_FOLDER_ID: Optional[str] = None
_PENDING_FOLDER_NAME = "Pending documents"
_APPROVED_FOLDER_NAME = "Approved documents"


def _build_service():
    """
    Build and return an authenticated Google Drive v3 service, or None.

    Tries OAuth2 with refresh token first (personal Google accounts),
    then falls back to service account (Shared Drives / Workspace only).
    """
    # --- Option 1: OAuth2 with refresh token (personal Google Drive) ---
    if _CLIENT_ID and _CLIENT_SECRET and _REFRESH_TOKEN:
        try:
            from google.oauth2.credentials import Credentials  # type: ignore
            from google.auth.transport.requests import Request  # type: ignore
            from googleapiclient.discovery import build  # type: ignore

            creds = Credentials(
                token=None,
                refresh_token=_REFRESH_TOKEN,
                client_id=_CLIENT_ID,
                client_secret=_CLIENT_SECRET,
                token_uri="https://oauth2.googleapis.com/token",
                scopes=_SCOPES,
            )
            creds.refresh(Request())
            logger.info("Google Drive: authenticated via OAuth2 (personal account)")
            return build("drive", "v3", credentials=creds)
        except Exception as exc:
            logger.warning("Google Drive OAuth2 build failed: %s", exc)
            # Do NOT fall through to service account — service accounts cannot
            # upload to personal My Drive (storageQuotaExceeded).  Return None
            # so the caller gets a clear error instead of a misleading 403.
            return None

    # --- Option 2: Service account (Shared Drives / Google Workspace ONLY) ---
    if _CREDENTIALS_JSON or _CREDENTIALS_PATH:
        try:
            from google.oauth2 import service_account  # type: ignore
            from googleapiclient.discovery import build  # type: ignore

            if _CREDENTIALS_JSON:
                info = json.loads(_CREDENTIALS_JSON)
                creds = service_account.Credentials.from_service_account_info(
                    info, scopes=_SCOPES
                )
            else:
                creds = service_account.Credentials.from_service_account_file(
                    _CREDENTIALS_PATH, scopes=_SCOPES
                )
            logger.info("Google Drive: authenticated via service account")
            return build("drive", "v3", credentials=creds)
        except Exception as exc:
            logger.warning("Google Drive service account build failed: %s", exc)

    return None


def get_drive_service():
    """Public helper to build an authenticated Google Drive service."""
    return _build_service()


def create_project_folder(
    project_name: str,
    parent_folder_id: Optional[str] = None,
) -> Optional[str]:
    """
    Create a subfolder in Google Drive for a project.

    Uses *parent_folder_id* if given, otherwise falls back to GOOGLE_DRIVE_FOLDER_ID.
    Returns the new folder's Drive ID, or None on failure / Drive not configured.
    """
    folder_info = create_project_folders(project_name, parent_folder_id)
    return folder_info.get("project_folder_id") if folder_info else None


def _find_folder(service, folder_name: str, parent_id: str) -> Optional[str]:
    """Find a folder by exact name under a parent. Returns folder ID or None."""
    try:
        query = (
            f"name='{folder_name}' and '{parent_id}' in parents "
            f"and mimeType='application/vnd.google-apps.folder' and trashed=false"
        )
        results = service.files().list(
            q=query,
            fields="files(id, name)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        files = results.get("files", [])
        if files:
            return files[0]["id"]
    except Exception as exc:
        logger.error("_find_folder('%s') failed: %s", folder_name, exc)
    return None


def find_or_create_folder(service, folder_name: str, parent_id: str) -> Optional[str]:
    """
    Find a folder by name under parent_id in Google Drive.
    Creates the folder if it does not exist. Returns the folder ID or None.
    """
    try:
        query = (
            f"name='{folder_name}' and '{parent_id}' in parents "
            f"and mimeType='application/vnd.google-apps.folder' and trashed=false"
        )
        results = service.files().list(
            q=query,
            fields="files(id, name)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        files = results.get("files", [])
        if files:
            logger.info("Found Drive folder '%s' → %s", folder_name, files[0]["id"])
            return files[0]["id"]
        # Not found — create it
        metadata: dict = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_id],
        }
        folder = service.files().create(body=metadata, fields="id", supportsAllDrives=True).execute()
        fid: str = folder.get("id", "")
        logger.info("Created Drive folder '%s' under %s → %s", folder_name, parent_id, fid)
        return fid or None
    except Exception as exc:
        logger.error("find_or_create_folder('%s') failed: %s", folder_name, exc)
        return None


def create_project_folders(
    project_name: str,
    parent_folder_id: Optional[str] = None,
) -> Optional[dict]:
    """
    Create (or reuse) project folder structure under root:
    Pending documents/[Project Name] and Approved documents/[Project Name]
    """
    service = _build_service()
    if service is None:
        logger.info("Google Drive not configured — skipping folder creation for '%s'", project_name)
        return None

    parent = parent_folder_id or _FOLDER_ID
    if not parent:
        logger.warning("GOOGLE_DRIVE_FOLDER_ID not set — cannot create project folders")
        return None

    try:
        pending_root_id = find_or_create_folder(service, _PENDING_FOLDER_NAME, parent)
        approved_root_id = find_or_create_folder(service, _APPROVED_FOLDER_NAME, parent)
        if not pending_root_id or not approved_root_id:
            return None

        pending_folder_id = find_or_create_folder(service, project_name, pending_root_id)
        approved_folder_id = find_or_create_folder(service, project_name, approved_root_id)

        if not pending_folder_id or not approved_folder_id:
            return None

        logger.info(
            "Project Drive folders ready for '%s': pending=%s approved=%s",
            project_name,
            pending_folder_id,
            approved_folder_id,
        )
        return {
            "project_folder_id": pending_folder_id,
            "pending_folder_id": pending_folder_id,
            "approved_folder_id": approved_folder_id,
        }
    except Exception as exc:
        logger.error("create_project_folders('%s') failed: %s", project_name, exc)
        return None


def get_project_folders(project_name: str, create_if_missing: bool = False) -> Optional[dict]:
    """
    Resolve project folders under Pending documents and Approved documents.
    By default this is read-only (no auto-creation).
    """
    service = _build_service()
    if service is None:
        return None
    if not _FOLDER_ID:
        return None

    pending_root_id, approved_root_id = get_root_folders(service)
    if not pending_root_id or not approved_root_id:
        return None

    if create_if_missing:
        pending_folder_id = find_or_create_folder(service, project_name, pending_root_id)
        approved_folder_id = find_or_create_folder(service, project_name, approved_root_id)
    else:
        pending_folder_id = _find_folder(service, project_name, pending_root_id)
        approved_folder_id = _find_folder(service, project_name, approved_root_id)

    if not pending_folder_id or not approved_folder_id:
        return None

    return {
        "project_folder_id": pending_folder_id,
        "pending_folder_id": pending_folder_id,
        "approved_folder_id": approved_folder_id,
    }


def get_root_folders(service) -> tuple:
    """
    Return (pending_folder_id, approved_folder_id).
    Creates 'Pending documents' and 'Approved documents' under GOOGLE_DRIVE_FOLDER_ID
    if they do not exist.
    """
    global _PENDING_FOLDER_ID, _APPROVED_FOLDER_ID

    if not _FOLDER_ID:
        logger.warning("GOOGLE_DRIVE_FOLDER_ID not set — cannot resolve root folders")
        return (None, None)

    if not _PENDING_FOLDER_ID:
        _PENDING_FOLDER_ID = find_or_create_folder(service, _PENDING_FOLDER_NAME, _FOLDER_ID)

    if not _APPROVED_FOLDER_ID:
        _APPROVED_FOLDER_ID = find_or_create_folder(service, _APPROVED_FOLDER_NAME, _FOLDER_ID)

    return (_PENDING_FOLDER_ID, _APPROVED_FOLDER_ID)


async def get_urs_templates_folder(service) -> Optional[str]:
    """
    Return Drive folder ID for 'URS Templates' under GOOGLE_DRIVE_FOLDER_ID.
    Creates it when missing.
    """
    global _URS_TEMPLATES_FOLDER_ID

    if not _FOLDER_ID:
        logger.warning("GOOGLE_DRIVE_FOLDER_ID not set — cannot resolve URS Templates folder")
        return None

    if not _URS_TEMPLATES_FOLDER_ID:
        _URS_TEMPLATES_FOLDER_ID = find_or_create_folder(service, "URS Templates", _FOLDER_ID)

    return _URS_TEMPLATES_FOLDER_ID


def upload_file(
    file_bytes: bytes,
    filename: str,
    mime_type: str = "application/octet-stream",
    project_name: Optional[str] = None,
) -> Optional[dict]:
    """
    Upload *file_bytes* to Google Drive under 'Pending documents/{project_name}/'.

    Returns {'file_id': str, 'view_link': str} on success, or None when Drive
    is not configured or the upload fails.
    """
    service = _build_service()
    if service is None:
        logger.info("Google Drive not configured — skipping upload for '%s'", filename)
        return None

    try:
        from googleapiclient.http import MediaIoBaseUpload  # type: ignore

        target_folder = _FOLDER_ID
        if project_name:
            folders = get_project_folders(project_name, create_if_missing=True)
            if folders and folders.get("pending_folder_id"):
                target_folder = folders["pending_folder_id"]
            else:
                pending_root_id, _approved_root_id = get_root_folders(service)
                if pending_root_id:
                    target_folder = pending_root_id
                logger.warning("Project folder not found for '%s'; using Pending documents root", project_name)

        metadata: dict = {"name": filename}
        if target_folder:
            metadata["parents"] = [target_folder]

        media = MediaIoBaseUpload(
            io.BytesIO(file_bytes), mimetype=mime_type, resumable=False
        )
        result = (
            service.files()
            .create(body=metadata, media_body=media, fields="id,webViewLink", supportsAllDrives=True)
            .execute()
        )
        file_id: str = result.get("id", "")
        view_link: str = result.get(
            "webViewLink",
            f"https://drive.google.com/file/d/{file_id}/view",
        )
        logger.info(
            "Uploaded '%s' to Pending documents/%s: %s",
            filename, project_name or "root", view_link,
        )
        return {"file_id": file_id, "view_link": view_link}
    except Exception as exc:
        logger.error("Google Drive upload failed for '%s': %s", filename, exc)
        return None


def move_file_to_approved(file_id: str, project_name: str) -> Optional[str]:
    """
    Move a Drive file from 'Pending documents/{project_name}' to
    'Approved documents/{project_name}'.

    Returns the new webViewLink on success, or None on failure.
    """
    service = _build_service()
    if service is None:
        logger.info("Google Drive not configured — skipping move for file %s", file_id)
        return None

    try:
        folders = get_project_folders(project_name, create_if_missing=False)
        if not folders or not folders.get("approved_folder_id"):
            logger.warning(
                "Approved folder not found for project '%s' — skipping move",
                project_name,
            )
            return None
        approved_project_id = folders["approved_folder_id"]

        # Get current parent folders of the file
        file_meta = service.files().get(fileId=file_id, fields="parents,name", supportsAllDrives=True).execute()
        current_parents = ",".join(file_meta.get("parents", []))

        # Move: add to approved project subfolder, remove from all current parents
        updated = service.files().update(
            fileId=file_id,
            addParents=approved_project_id,
            removeParents=current_parents,
            fields="id,webViewLink",
            supportsAllDrives=True,
        ).execute()
        new_link: str = updated.get(
            "webViewLink",
            f"https://drive.google.com/file/d/{file_id}/view",
        )
        logger.info(
            "Moved Drive file %s to Approved documents/%s: %s",
            file_id, project_name, new_link,
        )
        return new_link
    except Exception as exc:
        logger.error("move_file_to_approved failed for file %s: %s", file_id, exc)
        return None


# ---------------------------------------------------------------------------
# Helpers for editing files in-browser and watching for changes
# ---------------------------------------------------------------------------

_EDIT_URL_TEMPLATES: dict[str, str] = {
    # Google native formats
    "application/vnd.google-apps.document": "https://docs.google.com/document/d/{file_id}/edit",
    "application/vnd.google-apps.spreadsheet": "https://docs.google.com/spreadsheets/d/{file_id}/edit",
    "application/vnd.google-apps.presentation": "https://docs.google.com/presentation/d/{file_id}/edit",
    # Office formats (open-with)
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": (
        "https://docs.google.com/document/d/{file_id}/edit"
    ),
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": (
        "https://docs.google.com/spreadsheets/d/{file_id}/edit"
    ),
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": (
        "https://docs.google.com/presentation/d/{file_id}/edit"
    ),
    "application/msword": "https://docs.google.com/document/d/{file_id}/edit",
    "application/vnd.ms-excel": "https://docs.google.com/spreadsheets/d/{file_id}/edit",
    "application/vnd.ms-powerpoint": "https://docs.google.com/presentation/d/{file_id}/edit",
}


def get_drive_file_id(view_url: str) -> Optional[str]:
    """Extract the Drive file-ID from a webViewLink / any Drive URL."""
    import re

    match = re.search(r"/(?:file/d|document/d|spreadsheets/d|presentation/d)/([a-zA-Z0-9_-]+)", view_url)
    if match:
        return match.group(1)
    match = re.search(r"[?&]id=([a-zA-Z0-9_-]+)", view_url)
    return match.group(1) if match else None


def get_edit_url(view_url: str) -> Optional[str]:
    """
    Return an in-browser edit URL for a Drive file.

    For known editable Google/Office MIME types returns the Docs/Sheets/Slides
    edit URL.  Falls back to the ``view_url`` when the file is not editable
    (e.g. PDF) or when the Drive API is unavailable.
    """
    file_id = get_drive_file_id(view_url)
    if file_id is None:
        return view_url

    service = _build_service()
    if service is None:
        # Drive not configured — best-effort: swap /view → /edit
        return view_url.replace("/view", "/edit")

    try:
        meta = service.files().get(fileId=file_id, fields="id,mimeType").execute()
        mime = meta.get("mimeType", "")
        template = _EDIT_URL_TEMPLATES.get(mime)
        if template:
            return template.format(file_id=file_id)
        # Non-editable (PDF, image, …) — return view link as-is
        return view_url
    except Exception as exc:
        logger.warning("get_edit_url: could not fetch file metadata for %s: %s", file_id, exc)
        return view_url


def get_edit_url_for_mime(file_id: str, mime_type: str) -> str:
    """
    Return an edit/view URL for a Drive file based on its known MIME type.

    Simpler than get_edit_url() — no API call needed, works without Drive credentials.

    NOTE: Check spreadsheet/presentation BEFORE document because Office XML MIME types
    contain "officedocument" as a substring, which would falsely match "document" first.
    """
    mt = (mime_type or "").lower()
    # Spreadsheet check first (xlsx MIME contains "spreadsheetml", which starts with "spreadsheet")
    if "spreadsheet" in mt or "excel" in mt:
        return f"https://docs.google.com/spreadsheets/d/{file_id}/edit"
    if "presentation" in mt or "powerpoint" in mt:
        return f"https://docs.google.com/presentation/d/{file_id}/edit"
    # Word/Docs check last — "wordprocessingml" and "msword" both contain "word" but NOT "spreadsheet"
    if "wordprocessingml" in mt or "msword" in mt or (
        "document" in mt and "spreadsheet" not in mt and "presentation" not in mt
    ):
        return f"https://docs.google.com/document/d/{file_id}/edit"
    # Non-editable (PDF, image, audio, etc.) → Drive view link
    return f"https://drive.google.com/file/d/{file_id}/view"


def register_file_watch(file_id: str, webhook_url: str, channel_id: Optional[str] = None) -> Optional[dict]:
    """
    Register a Drive push-notification channel for *file_id*.

    Returns the channel metadata dict on success, or None when Drive is not
    configured or the call fails.
    """
    import uuid as _uuid

    service = _build_service()
    if service is None:
        return None

    body = {
        "id": channel_id or str(_uuid.uuid4()),
        "type": "web_hook",
        "address": webhook_url,
    }
    try:
        channel = service.files().watch(fileId=file_id, body=body).execute()
        logger.info("Drive watch registered for file %s → channel %s", file_id, channel.get("id"))
        return channel
    except Exception as exc:
        logger.error("register_file_watch failed for file %s: %s", file_id, exc)
        return None
