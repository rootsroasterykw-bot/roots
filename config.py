"""
WhatsApp Secretary — Configuration
Fill in your credentials before running the server.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Twilio ──────────────────────────────────────────────────────────────────
TWILIO_ACCOUNT_SID   = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN    = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")  # sandbox default

# ── Anthropic (Claude AI) ───────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# ── Google ──────────────────────────────────────────────────────────────────
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "google_credentials.json")

# Google Drive — Sector Folder IDs
# After creating folders in Drive, paste each folder's ID here.
# Get it from the URL: drive.google.com/drive/folders/FOLDER_ID_HERE
DRIVE_FOLDER_IDS = {
    "financial":  os.getenv("DRIVE_FOLDER_FINANCIAL",  ""),
    "operations": os.getenv("DRIVE_FOLDER_OPERATIONS",  ""),
    "logistics":  os.getenv("DRIVE_FOLDER_LOGISTICS",   ""),
    "purchasing": os.getenv("DRIVE_FOLDER_PURCHASING",  ""),
    "marketing":  os.getenv("DRIVE_FOLDER_MARKETING",   ""),
}

# Google Sheets — Spreadsheet IDs
# Get them from the sheet URL: docs.google.com/spreadsheets/d/SHEET_ID_HERE/edit
SHEET_IDS = {
    "financial":  os.getenv("SHEET_ID_FINANCIAL",  ""),
    "operations": os.getenv("SHEET_ID_OPERATIONS",  ""),
    "logistics":  os.getenv("SHEET_ID_LOGISTICS",   ""),
    "purchasing": os.getenv("SHEET_ID_PURCHASING",  ""),
    "marketing":  os.getenv("SHEET_ID_MARKETING",   ""),
}

# ── Sector Menu ─────────────────────────────────────────────────────────────
SECTORS = {
    "1": "financial",
    "2": "operations",
    "3": "logistics",
    "4": "purchasing",
    "5": "marketing",
}

SECTOR_MENU = (
    "📂 *Which sector is this file for?*\n\n"
    "1️⃣  Financial\n"
    "2️⃣  Operations\n"
    "3️⃣  Logistics\n"
    "4️⃣  Purchasing\n"
    "5️⃣  Marketing\n\n"
    "Reply with the number (1–5)"
)
