"""
Google Sheets service for backlog tracking.

Columns in the AI-BA-Agent backlog sheet:
  A: No.
  B: User Name
  C: Project Name
  D: File name (without extension)
  E: Upload date  (DD-Mon-YYYY, e.g. 20-Mar-2026)
  F: Approver
  G: Approval status
  H: Approver comment

Uses the same OAuth2 credentials as google_drive.py.
Required env vars:
  GOOGLE_SHEETS_ID      — spreadsheet ID
  GOOGLE_CLIENT_ID      — OAuth2 client ID
  GOOGLE_CLIENT_SECRET  — OAuth2 client secret
  GOOGLE_REFRESH_TOKEN  — refresh token obtained with BOTH scopes:
                           drive.file + spreadsheets

⚠️  If the current GOOGLE_REFRESH_TOKEN was obtained with only the
    drive.file scope, Sheets calls will fail silently.
    Re-run backend/scripts/get_google_refresh_token.py (updated to
    request both scopes) to generate a new token.
"""
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_SHEETS_ID: str = os.environ.get("GOOGLE_SHEETS_ID", "")
_CLIENT_ID: str = os.environ.get("GOOGLE_CLIENT_ID", "")
_CLIENT_SECRET: str = os.environ.get("GOOGLE_CLIENT_SECRET", "")
_REFRESH_TOKEN: str = os.environ.get("GOOGLE_REFRESH_TOKEN", "")

# Both scopes must be authorised in the refresh token
_SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/spreadsheets",
]


def _build_sheets_service():
    """Return an authenticated Sheets v4 service, or None."""
    if not (_CLIENT_ID and _CLIENT_SECRET and _REFRESH_TOKEN and _SHEETS_ID):
        return None
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
        logger.info("Google Sheets: authenticated via OAuth2")
        return build("sheets", "v4", credentials=creds)
    except Exception as exc:
        logger.warning("Google Sheets service build failed: %s", exc)
        return None


def find_row_by_document(project_name: str, file_name: str) -> Optional[int]:
    """
    Search columns C and D for a matching (project_name, file_name) pair.
    Returns the 1-based row number, or None if not found.
    """
    service = _build_sheets_service()
    if service is None:
        return None
    try:
        result = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=_SHEETS_ID, range="A:H")
            .execute()
        )
        rows = result.get("values", [])
        for i, row in enumerate(rows):
            c = row[2] if len(row) > 2 else ""
            d = row[3] if len(row) > 3 else ""
            if c == project_name and d == file_name:
                return i + 1  # Sheets rows are 1-indexed
        return None
    except Exception as exc:
        logger.warning("Sheets find_row_by_document failed: %s", exc)
        return None


def append_upload_row(
    user_name: str,
    project_name: str,
    file_name: str,
    upload_date: str,
) -> None:
    """
    Append a new row to the backlog sheet when a file is uploaded.

    Columns: No. | User Name | Project Name | File Name | Upload Date | (blank) | Pending | /
    """
    service = _build_sheets_service()
    if service is None:
        logger.info("Google Sheets not configured — skipping upload row for '%s'", file_name)
        return
    try:
        # Count existing rows to auto-increment the No. column
        count_result = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=_SHEETS_ID, range="A:A")
            .execute()
        )
        next_no = max(1, len(count_result.get("values", [])))

        row = [str(next_no), user_name, project_name, file_name, upload_date, "/", "Pending", "/"]
        service.spreadsheets().values().append(
            spreadsheetId=_SHEETS_ID,
            range="A:H",
            valueInputOption="USER_ENTERED",
            body={"values": [row]},
        ).execute()
        logger.info("Sheets: appended row %d — '%s' / '%s'", next_no, project_name, file_name)
    except Exception as exc:
        logger.warning("Sheets append_upload_row failed: %s", exc)


def update_approval_row(
    project_name: str,
    file_name: str,
    approver_name: str,
    status: str,
    comment: str = "",
) -> None:
    """
    Update columns F, G, H for the row matching (project_name, file_name).

      F: approver_name  (blank when no action taken yet)
      G: status  ("Pending" | "Awaiting Resubmission" | "Resubmitted" | "Approved" | "Rejected")
      H: comment  (defaults to "/" when empty)
    """
    service = _build_sheets_service()
    if service is None:
        logger.info("Google Sheets not configured — skipping approval update for '%s'", file_name)
        return
    try:
        row_num = find_row_by_document(project_name, file_name)
        if row_num is None:
            logger.warning(
                "Sheets: no row found for project='%s' file='%s' — skipping update",
                project_name,
                file_name,
            )
            return

        service.spreadsheets().values().update(
            spreadsheetId=_SHEETS_ID,
            range=f"F{row_num}:H{row_num}",
            valueInputOption="USER_ENTERED",
            body={"values": [[approver_name, status, comment if comment else "/"]]},
        ).execute()
        logger.info("Sheets: updated row %d — '%s' → %s", row_num, file_name, status)
    except Exception as exc:
        logger.warning("Sheets update_approval_row failed: %s", exc)
