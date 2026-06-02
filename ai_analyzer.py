"""
WhatsApp Secretary — AI Document Analyzer
Uses Claude Vision API to extract structured data from any document type.
"""

import anthropic
import base64
from config import ANTHROPIC_API_KEY

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


SECTOR_PROMPTS = {
    "financial": """
You are analyzing a financial document (invoice, receipt, bill, or payment record).
Extract ALL of the following fields. If a field is not found, write "N/A".
Return ONLY a JSON object with these exact keys:
{
  "date": "",
  "company_name": "",
  "invoice_number": "",
  "description": "",
  "amount_excl_tax": "",
  "tax": "",
  "total_amount": "",
  "currency": "",
  "payment_status": "",
  "notes": ""
}
Be precise. Include currency symbols. For payment_status use: Paid / Unpaid / Partial.
""",

    "purchasing": """
You are analyzing a purchasing document (purchase order, delivery note, or supplier invoice).
Extract ALL of the following fields. If a field is not found, write "N/A".
Return ONLY a JSON object with these exact keys:
{
  "date": "",
  "supplier": "",
  "po_number": "",
  "items": "",
  "unit_price": "",
  "quantity": "",
  "total_cost": "",
  "delivery_date": "",
  "status": "",
  "notes": ""
}
For items: list all items separated by semicolons if multiple.
For status use: Ordered / Delivered / Pending / Partial.
""",

    "logistics": """
You are analyzing a logistics or shipping document (waybill, bill of lading, delivery receipt, tracking document).
Extract ALL of the following fields. If a field is not found, write "N/A".
Return ONLY a JSON object with these exact keys:
{
  "date": "",
  "carrier_company": "",
  "tracking_number": "",
  "origin": "",
  "destination": "",
  "description": "",
  "weight_volume": "",
  "shipping_cost": "",
  "eta": "",
  "status": ""
}
For status use: In Transit / Delivered / Pending / Customs Hold.
""",

    "operations": """
You are analyzing an operations document (maintenance report, work order, official letter, contract, permit, or internal memo).
Extract ALL of the following fields. If a field is not found, write "N/A".
Return ONLY a JSON object with these exact keys:
{
  "date": "",
  "document_type": "",
  "related_department": "",
  "description": "",
  "action_required": "",
  "assigned_to": "",
  "due_date": "",
  "status": "",
  "notes": ""
}
For document_type: identify what kind of document this is.
For status use: Open / Closed / Pending / In Progress.
""",

    "marketing": """
You are analyzing a marketing document (campaign proposal, agency invoice, design brief, media plan, or advertisement).
Extract ALL of the following fields. If a field is not found, write "N/A".
Return ONLY a JSON object with these exact keys:
{
  "date": "",
  "campaign_project": "",
  "vendor_agency": "",
  "document_type": "",
  "amount": "",
  "platform_channel": "",
  "deadline": "",
  "status": "",
  "notes": ""
}
For status use: Active / Completed / Draft / Pending Approval.
"""
}


def analyze_document(file_bytes: bytes, sector: str, media_type: str = "image/jpeg") -> dict:
    """
    Analyze file bytes with Claude Vision.
    file_bytes: already-downloaded raw bytes of the file.
    media_type: MIME type string.
    Returns a dict of extracted fields.
    """

    b64_data = base64.standard_b64encode(file_bytes).decode("utf-8")
    prompt = SECTOR_PROMPTS.get(sector, SECTOR_PROMPTS["financial"])

    # Build message depending on file type
    if "pdf" in media_type:
        # Claude supports PDF as document type
        message = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": b64_data,
                        },
                    },
                    {"type": "text", "text": prompt}
                ],
            }],
        )
    else:
        # Image
        message = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": b64_data,
                        },
                    },
                    {"type": "text", "text": prompt}
                ],
            }],
        )

    raw = message.content[0].text.strip()

    # Extract JSON from response
    import json, re
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return {"error": "Could not parse AI response", "raw": raw[:500]}
