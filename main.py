"""
WhatsApp Secretary — Main FastAPI Application
Handles Twilio WhatsApp webhooks, sector routing, AI analysis, and logging.
"""

import requests as req_lib
import datetime
import asyncio
import traceback
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, Form, Request, BackgroundTasks
from fastapi.responses import PlainTextResponse
from twilio.rest import Client as TwilioClient
from twilio.request_validator import RequestValidator

from config import (
    TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM,
    SECTORS, SECTOR_MENU
)
from ai_analyzer import analyze_document
from google_services import upload_to_drive, append_to_sheet

app = FastAPI(title="WhatsApp Secretary")

twilio_client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
_executor = ThreadPoolExecutor(max_workers=4)

# ── In-memory session state ──────────────────────────────────────────────────
# Format: { "whatsapp:+96599XXXXXX": { "stage": "awaiting_sector", "file_url": ..., ... } }
sessions: dict = {}


def _send_whatsapp_sync(to: str, message: str):
    """Synchronous Twilio send (called in thread pool to avoid blocking event loop)."""
    twilio_client.messages.create(
        from_=TWILIO_WHATSAPP_FROM,
        to=to,
        body=message,
    )


async def send_whatsapp(to: str, message: str):
    """Send a WhatsApp message via Twilio (non-blocking)."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(_executor, _send_whatsapp_sync, to, message)


def process_file_background(sender: str, file_url: str, sector: str,
                             content_type: str, original_filename: str):
    """
    Background task: analyze file with Claude, upload to Drive, log to Sheets.
    Runs after we've already replied to Twilio with 200 OK.
    Uses _send_whatsapp_sync (not the async wrapper) since this runs in a thread.
    """
    sector_label = sector.capitalize()
    # Twilio requires Basic Auth to download media files
    twilio_auth = (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    try:
        _send_whatsapp_sync(sender, f"⏳ Analyzing your file for *{sector_label}* sector...")

        # 1. Download file bytes — requests follows CDN redirects automatically
        response = req_lib.get(file_url, auth=twilio_auth, timeout=30)
        response.raise_for_status()
        file_bytes = response.content

        # 2. Build filename
        ext = _guess_extension(content_type, original_filename)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{sector}_{timestamp}{ext}"

        # 3. Upload to Google Drive
        drive_link = upload_to_drive(file_bytes, filename, content_type, sector)

        # 4. Analyze with Claude AI (pass already-downloaded bytes — no second download)
        extracted = analyze_document(file_bytes, sector, content_type)

        if "error" in extracted:
            _send_whatsapp_sync(
                sender,
                f"⚠️ File saved to Drive but AI couldn't fully read it.\n"
                f"📁 File: {drive_link}\n\n"
                f"Please check it manually in your *{sector_label}* folder."
            )
            return

        # 5. Log to Google Sheets
        append_to_sheet(extracted, sector, drive_link)

        # 6. Build confirmation summary
        summary = _build_summary(extracted, sector)
        _send_whatsapp_sync(
            sender,
            f"✅ *Done! Filed to {sector_label}*\n\n"
            f"{summary}\n"
            f"📁 *File:* {drive_link}"
        )

    except Exception as e:
        tb = traceback.format_exc()
        print(f"\n🔴 ERROR in process_file_background for {sender}:\n{tb}\n")
        _send_whatsapp_sync(
            sender,
            f"❌ Something went wrong processing your file.\n"
            f"Error: {str(e)[:200]}\n\n"
            f"Please try again or contact support."
        )


def _guess_extension(content_type: str, filename: str) -> str:
    if filename and "." in filename:
        return "." + filename.rsplit(".", 1)[-1].lower()
    if "pdf" in content_type:
        return ".pdf"
    if "jpeg" in content_type or "jpg" in content_type:
        return ".jpg"
    if "png" in content_type:
        return ".png"
    return ".bin"


def _build_summary(data: dict, sector: str) -> str:
    """Build a short human-readable summary from extracted data."""
    lines = []
    key_map = {
        "financial":  [("company_name","🏢"), ("date","📅"), ("total_amount","💰"), ("payment_status","💳")],
        "purchasing": [("supplier","🏢"), ("date","📅"), ("total_cost","💰"), ("status","📦")],
        "logistics":  [("carrier_company","🚚"), ("date","📅"), ("tracking_number","🔢"), ("status","📍")],
        "operations": [("document_type","📄"), ("date","📅"), ("description","📝"), ("status","🔄")],
        "marketing":  [("campaign_project","📣"), ("date","📅"), ("amount","💰"), ("status","🔄")],
    }
    for key, icon in key_map.get(sector, []):
        val = data.get(key, "N/A")
        if val and val != "N/A":
            label = key.replace("_", " ").title()
            lines.append(f"{icon} *{label}:* {val}")
    return "\n".join(lines) if lines else "Data logged to sheet."


# ── Webhook endpoint ─────────────────────────────────────────────────────────

@app.post("/webhook", response_class=PlainTextResponse)
async def whatsapp_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    From: str = Form(default=""),
    Body: str = Form(default=""),
    NumMedia: str = Form(default="0"),
    MediaUrl0: str = Form(default=""),
    MediaContentType0: str = Form(default=""),
    MediaUrl1: str = Form(default=""),
    MediaContentType1: str = Form(default=""),
):
    sender = From.strip()
    text = Body.strip().lower()
    num_media = int(NumMedia or 0)

    session = sessions.get(sender, {})

    # ── Case 1: File received ────────────────────────────────────────────────
    if num_media > 0 and MediaUrl0:
        sessions[sender] = {
            "stage": "awaiting_sector",
            "file_url": MediaUrl0,
            "content_type": MediaContentType0 or "image/jpeg",
            "filename": _guess_filename_from_url(MediaUrl0),
        }
        await send_whatsapp(sender, SECTOR_MENU)
        return PlainTextResponse("")

    # ── Case 2: Sector selection ─────────────────────────────────────────────
    if session.get("stage") == "awaiting_sector":
        if text in SECTORS:
            sector = SECTORS[text]
            file_url     = session["file_url"]
            content_type = session.get("content_type", "image/jpeg")
            filename     = session.get("filename", "document")

            # Clear session
            sessions.pop(sender, None)

            await send_whatsapp(sender, f"✅ Got it — filing to *{sector.capitalize()}* sector...")

            # Process in background so we return 200 immediately
            background_tasks.add_task(
                process_file_background,
                sender, file_url, sector, content_type, filename
            )
            return PlainTextResponse("")

        else:
            await send_whatsapp(
                sender,
                "❓ Please reply with a number *1–5*:\n\n" + SECTOR_MENU
            )
            return PlainTextResponse("")

    # ── Case 3: Text message with no pending file ────────────────────────────
    if text in ("hi", "hello", "مرحبا", "السلام عليكم"):
        await send_whatsapp(
            sender,
            "👋 *Hello Hasan!*\n\n"
            "I'm your WhatsApp Secretary 🤖\n\n"
            "Send me any file (invoice, photo, PDF) and I'll:\n"
            "✅ Ask you which sector\n"
            "✅ Save it to Google Drive\n"
            "✅ Analyze it with AI\n"
            "✅ Log it to your Google Sheet\n\n"
            "Ready when you are!"
        )
    else:
        await send_whatsapp(
            sender,
            "📎 Please send me a *file or image* to get started.\n\n"
            "I accept: PDFs, photos, invoices, receipts, any document."
        )

    return PlainTextResponse("")


def _guess_filename_from_url(url: str) -> str:
    try:
        part = url.split("?")[0].split("/")[-1]
        return part if part else "document"
    except Exception:
        return "document"


@app.get("/health")
def health():
    return {"status": "ok", "service": "WhatsApp Secretary"}
