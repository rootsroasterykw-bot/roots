"""
WhatsApp Secretary — Google Drive & Sheets Integration
Uploads files to Drive and logs extracted data to Sheets.
"""

import io
import datetime
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2 import service_account
from config import GOOGLE_CREDENTIALS_FILE, DRIVE_FOLDER_IDS, SHEET_IDS

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]


def _get_credentials():
    return service_account.Credentials.from_service_account_file(
        GOOGLE_CREDENTIALS_FILE, scopes=SCOPES
    )


def upload_to_drive(file_bytes: bytes, filename: str, mime_type: str, sector: str) -> str:
    """Upload a file to the correct sector folder. Returns the public view URL."""
    creds = _get_credentials()
    service = build("drive", "v3", credentials=creds)

    folder_id = DRIVE_FOLDER_IDS.get(sector)
    if not folder_id:
        raise ValueError(f"No Drive folder configured for sector: {sector}")

    file_metadata = {
        "name": filename,
        "parents": [folder_id],
    }
    media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type, resumable=True)

    uploaded = service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id, webViewLink"
    ).execute()

    file_id = uploaded.get("id")

    # Make it viewable by anyone with the link
    service.permissions().create(
        fileId=file_id,
        body={"type": "anyone", "role": "reader"},
    ).execute()

    return uploaded.get("webViewLink", f"https://drive.google.com/file/d/{file_id}/view")


# ── Column mappings per sector ───────────────────────────────────────────────

SHEET_COLUMNS = {
    "financial": [
        "date", "company_name", "invoice_number", "description",
        "amount_excl_tax", "tax", "total_amount", "currency",
        "payment_status", "file_link", "notes"
    ],
    "purchasing": [
        "date", "supplier", "po_number", "items",
        "unit_price", "quantity", "total_cost",
        "delivery_date", "status", "file_link", "notes"
    ],
    "logistics": [
        "date", "carrier_company", "tracking_number", "origin",
        "destination", "description", "weight_volume",
        "shipping_cost", "eta", "status", "file_link"
    ],
    "operations": [
        "date", "document_type", "related_department", "description",
        "action_required", "assigned_to", "due_date",
        "status", "file_link", "notes"
    ],
    "marketing": [
        "date", "campaign_project", "vendor_agency", "document_type",
        "amount", "platform_channel", "deadline",
        "status", "file_link", "notes"
    ],
}


def append_to_sheet(data: dict, sector: str, file_link: str) -> bool:
    """Append a row to the correct sector Google Sheet."""
    creds = _get_credentials()
    service = build("sheets", "v4", credentials=creds)

    sheet_id = SHEET_IDS.get(sector)
    if not sheet_id:
        raise ValueError(f"No Sheet configured for sector: {sector}")

    columns = SHEET_COLUMNS.get(sector, [])
    data["file_link"] = file_link

    row = []
    for col in columns:
        val = data.get(col, "N/A")
        if not val or val == "":
            val = "N/A"
        row.append(str(val))

    body = {"values": [row]}
    service.spreadsheets().values().append(
        spreadsheetId=sheet_id,
        range="A:Z",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body=body,
    ).execute()

    return True
