"""
Claude API service for document extraction.

Supports:
- Text-only extraction (text-based PDFs, CSVs)
- Vision extraction (scanned PDFs, images)
- Freight invoice and Bill of Lading document types
- 2-pass extraction (raw extract → self-review refinement)
"""

import json
import logging

import anthropic

from app.config import Settings
from app.schemas.extraction import (
    BillOfLadingExtraction,
    DocumentType,
    FreightInvoiceExtraction,
)

logger = logging.getLogger("gamma.claude")

EXTRACTION_SYSTEM_PROMPT = """You are a logistics document extraction specialist. Your job is to extract structured data from freight invoices, bills of lading, warehouse receipts, and other logistics documents.

Extract all available information accurately. If a field is not present in the document, use null. For monetary amounts, use numeric values without currency symbols. For dates, use ISO 8601 format (YYYY-MM-DD).

Respond with valid JSON only, no additional text."""

FREIGHT_INVOICE_SCHEMA = """{
  "invoice_number": "string",
  "invoice_date": "YYYY-MM-DD or null",
  "vendor_name": "string",
  "shipper_name": "string or null",
  "consignee_name": "string or null",
  "origin": "string or null",
  "destination": "string or null",
  "currency": "USD",
  "line_items": [{"description": "string", "quantity": 0, "unit": "string", "unit_price": 0, "total": 0}],
  "subtotal": 0,
  "tax_amount": 0,
  "total_amount": 0,
  "notes": "string or null"
}"""

BOL_SCHEMA = """{
  "bol_number": "string",
  "issue_date": "YYYY-MM-DD or null",
  "carrier_name": "string or null",
  "carrier_scac": "string or null",
  "shipper": {"name": "string", "address": "string or null"},
  "consignee": {"name": "string", "address": "string or null"},
  "notify_party": "string or null",
  "origin": {"city": "string or null", "state": "string or null", "country": "string or null", "port": "string or null"},
  "destination": {"city": "string or null", "state": "string or null", "country": "string or null", "port": "string or null"},
  "vessel_name": "string or null",
  "voyage_number": "string or null",
  "container_numbers": ["string"],
  "cargo_description": "string or null",
  "package_count": 0,
  "gross_weight": 0,
  "weight_unit": "kg or lbs",
  "volume": 0,
  "volume_unit": "CBM or CFT",
  "freight_charges": 0,
  "freight_payment_type": "prepaid or collect",
  "special_instructions": "string or null",
  "notes": "string or null"
}"""

REVIEW_SYSTEM_PROMPT = """You are a logistics document extraction quality reviewer. You will receive:
1. The original document content
2. A first-pass extraction result (JSON)

Your job is to review the extraction for accuracy and correct any errors. Common issues:
- Misread numbers (transposed digits, decimal errors)
- Wrong dates or date formats
- Line item totals that don't match quantity × unit_price
- Missing fields that are actually present in the document
- Incorrect party assignments (shipper vs consignee)

Output the corrected JSON extraction. If the original extraction is correct, return it unchanged.
Respond with valid JSON only, no additional text."""


def _parse_json_response(response_text: str) -> dict:
    """Parse JSON from Claude response, handling markdown code blocks."""
    text = response_text.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    try:
        return json.loads(text)
    except (json.JSONDecodeError, IndexError) as e:
        logger.error("Failed to parse Claude response as JSON: %s", e)
        raise ValueError(f"Claude response was not valid JSON: {e}") from e


def _get_schema_for_type(doc_type: DocumentType) -> str:
    """Get the JSON schema template for a document type."""
    if doc_type == DocumentType.BILL_OF_LADING:
        return BOL_SCHEMA
    return FREIGHT_INVOICE_SCHEMA


def _build_content(
    text: str = "", images: list[dict] | None = None, extra_text: str = ""
) -> list[dict]:
    """Build Claude message content array supporting text and vision."""
    content: list[dict] = []

    if images:
        for img in images:
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": img["media_type"],
                    "data": img["base64"],
                },
            })

    text_parts = []
    if text.strip():
        text_parts.append(text)
    if extra_text.strip():
        text_parts.append(extra_text)

    if text_parts:
        content.append({"type": "text", "text": "\n\n".join(text_parts)})

    return content


class ClaudeService:
    def __init__(self, settings: Settings):
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.model = settings.claude_model
        self.max_tokens = settings.claude_max_tokens

    async def extract(
        self,
        doc_type: DocumentType,
        text: str = "",
        images: list[dict] | None = None,
    ) -> dict:
        """Extract structured data from a document (Pass 1).

        Args:
            doc_type: Type of document to extract.
            text: Document text content.
            images: List of {"base64": str, "media_type": str} for vision.

        Returns:
            Extracted data as a dict (validated against Pydantic model).
        """
        schema = _get_schema_for_type(doc_type)
        prompt = f"Extract all structured information from this logistics document into the following JSON structure:\n\n{schema}\n\nDocument content:"

        content = _build_content(text=text, images=images, extra_text=prompt if not text and images else "")

        # If we have text, prepend the prompt
        if text.strip():
            full_text = f"{prompt}\n\n{text}"
            content = _build_content(images=images, extra_text=full_text)

        message = await self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=EXTRACTION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content}],
        )

        result = _parse_json_response(message.content[0].text)

        # Validate against Pydantic model
        if doc_type == DocumentType.BILL_OF_LADING:
            validated = BillOfLadingExtraction.model_validate(result)
        else:
            validated = FreightInvoiceExtraction.model_validate(result)

        return validated.model_dump(mode="json")

    async def review_extraction(
        self,
        doc_type: DocumentType,
        raw_extraction: dict,
        text: str = "",
        images: list[dict] | None = None,
    ) -> dict:
        """Review and refine a first-pass extraction (Pass 2).

        Args:
            doc_type: Document type.
            raw_extraction: Pass 1 extraction result.
            text: Original document text.
            images: Original document images.

        Returns:
            Refined extraction as a dict.
        """
        review_prompt = (
            f"Original document content:\n\n{text}\n\n"
            f"First-pass extraction result:\n\n{json.dumps(raw_extraction, indent=2, default=str)}\n\n"
            "Review the extraction above against the original document. "
            "Correct any errors and return the final JSON."
        )

        content = _build_content(images=images, extra_text=review_prompt)

        message = await self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=REVIEW_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content}],
        )

        result = _parse_json_response(message.content[0].text)

        # Validate against Pydantic model
        if doc_type == DocumentType.BILL_OF_LADING:
            validated = BillOfLadingExtraction.model_validate(result)
        else:
            validated = FreightInvoiceExtraction.model_validate(result)

        return validated.model_dump(mode="json")

    # Legacy method for backward compatibility with Phase 1 tests
    async def extract_freight_invoice(
        self, document_text: str
    ) -> FreightInvoiceExtraction:
        """Extract structured freight invoice data from document text."""
        result = await self.extract(
            doc_type=DocumentType.FREIGHT_INVOICE, text=document_text
        )
        return FreightInvoiceExtraction.model_validate(result)
