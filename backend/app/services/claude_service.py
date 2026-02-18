"""
Claude API service for document extraction.

Supports:
- Text-only extraction (text-based PDFs, CSVs)
- Vision extraction (scanned PDFs, images)
- All 11 logistics document types
- 2-pass extraction (raw extract -> self-review refinement)
"""

import json
import logging

import anthropic

from app.config import Settings
from app.schemas.extraction import (
    DocumentType,
    EXTRACTION_MODEL_REGISTRY,
    FreightInvoiceExtraction,
)

logger = logging.getLogger("gamma.claude")

EXTRACTION_SYSTEM_PROMPT = """You are a logistics document extraction specialist. Your job is to extract structured data from freight invoices, bills of lading, commercial invoices, purchase orders, packing lists, arrival notices, air waybills, debit/credit notes, customs entry summaries, proofs of delivery, certificates of origin, and other logistics documents.

Extract all available information accurately. If a field is not present in the document, use null. For monetary amounts, use numeric values without currency symbols. For dates, use ISO 8601 format (YYYY-MM-DD).

Respond with valid JSON only, no additional text."""

REVIEW_SYSTEM_PROMPT = """You are a logistics document extraction quality reviewer. You will receive:
1. The original document content
2. A first-pass extraction result (JSON)

Your job is to review the extraction for accuracy and correct any errors. Common issues:
- Misread numbers (transposed digits, decimal errors)
- Wrong dates or date formats
- Line item totals that don't match quantity x unit_price
- Missing fields that are actually present in the document
- Incorrect party assignments (shipper vs consignee)

Output the corrected JSON extraction. If the original extraction is correct, return it unchanged.
Respond with valid JSON only, no additional text."""

# --- JSON Schema Templates ---
# Maps DocumentType to a JSON template string that guides Claude's extraction.

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
  "notes": "string or null",
  "invoice_variant": "standard|detention_demurrage|accessorial|consolidated|pro_forma or null",
  "demurrage_details": [{"container_number": "string", "free_time_days": 0, "free_time_start": "YYYY-MM-DD", "free_time_end": "YYYY-MM-DD", "charge_start_date": "YYYY-MM-DD", "charge_end_date": "YYYY-MM-DD", "daily_rate": 0, "total_chargeable_days": 0, "fmc_compliance_statement": false}]
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

COMMERCIAL_INVOICE_SCHEMA = """{
  "invoice_number": "string",
  "invoice_date": "YYYY-MM-DD or null",
  "seller": {"name": "string", "address": "string or null", "city": "string or null", "state": "string or null", "country": "string or null", "postal_code": "string or null", "tax_id": "string or null", "contact_name": "string or null", "phone": "string or null", "email": "string or null"},
  "buyer": {"name": "string", "address": "string or null", "city": "string or null", "state": "string or null", "country": "string or null", "postal_code": "string or null", "tax_id": "string or null", "contact_name": "string or null", "phone": "string or null", "email": "string or null"},
  "consignee": null,
  "ship_from": {"city": "string or null", "state": "string or null", "country": "string or null", "port": "string or null"},
  "ship_to": {"city": "string or null", "state": "string or null", "country": "string or null", "port": "string or null"},
  "country_of_origin": "string or null",
  "country_of_export": "string or null",
  "currency": "USD",
  "incoterms": "string or null",
  "incoterms_location": "string or null",
  "payment_terms": "string or null",
  "line_items": [{"item_number": "string or null", "description": "string", "hs_code": "string or null", "country_of_origin": "string or null", "quantity": 0, "unit": "string", "unit_price": 0, "total": 0}],
  "subtotal": 0,
  "freight_charges": 0,
  "insurance_charges": 0,
  "discount_amount": 0,
  "tax_amount": 0,
  "total_amount": 0,
  "transport_reference": "string or null",
  "vessel_or_flight": "string or null",
  "export_reason": "string or null",
  "notes": "string or null",
  "invoice_variant": "standard|pro_forma or null"
}"""

PURCHASE_ORDER_SCHEMA = """{
  "po_number": "string",
  "po_date": "YYYY-MM-DD or null",
  "buyer": {"name": "string", "address": "string or null", "city": "string or null", "state": "string or null", "country": "string or null", "postal_code": "string or null", "tax_id": "string or null", "contact_name": "string or null", "phone": "string or null", "email": "string or null"},
  "supplier": {"name": "string", "address": "string or null", "city": "string or null", "state": "string or null", "country": "string or null", "postal_code": "string or null", "tax_id": "string or null", "contact_name": "string or null", "phone": "string or null", "email": "string or null"},
  "ship_to": null,
  "currency": "USD",
  "incoterms": "string or null",
  "incoterms_location": "string or null",
  "payment_terms": "string or null",
  "delivery_date": "YYYY-MM-DD or null",
  "shipping_method": "string or null",
  "line_items": [{"line_number": 0, "item_number": "string or null", "description": "string", "hs_code": "string or null", "quantity": 0, "unit": "string", "unit_price": 0, "total": 0}],
  "subtotal": 0,
  "tax_amount": 0,
  "shipping_amount": 0,
  "total_amount": 0,
  "notes": "string or null",
  "status": "string or null"
}"""

PACKING_LIST_SCHEMA = """{
  "packing_list_number": "string or null",
  "packing_date": "YYYY-MM-DD or null",
  "invoice_number": "string or null",
  "po_number": "string or null",
  "seller": {"name": "string", "address": "string or null", "city": "string or null", "state": "string or null", "country": "string or null", "postal_code": "string or null", "tax_id": "string or null", "contact_name": "string or null", "phone": "string or null", "email": "string or null"},
  "buyer": null,
  "consignee": null,
  "ship_from": {"city": "string or null", "state": "string or null", "country": "string or null", "port": "string or null"},
  "ship_to": {"city": "string or null", "state": "string or null", "country": "string or null", "port": "string or null"},
  "transport_reference": "string or null",
  "vessel_or_flight": "string or null",
  "container_numbers": ["string"],
  "items": [{"item_number": "string or null", "description": "string", "quantity": 0, "unit": "string or null", "package_type": "string or null", "package_count": 0, "gross_weight": 0, "net_weight": 0, "dimensions": "string or null", "marks": "string or null"}],
  "total_packages": 0,
  "total_gross_weight": 0,
  "total_net_weight": 0,
  "weight_unit": "kg or lbs",
  "total_volume": 0,
  "volume_unit": "CBM or CFT",
  "marks_and_numbers": "string or null",
  "notes": "string or null"
}"""

ARRIVAL_NOTICE_SCHEMA = """{
  "notice_number": "string or null",
  "notice_date": "YYYY-MM-DD or null",
  "carrier": {"name": "string", "address": "string or null", "city": "string or null", "state": "string or null", "country": "string or null", "postal_code": "string or null", "tax_id": "string or null", "contact_name": "string or null", "phone": "string or null", "email": "string or null"},
  "shipper": null,
  "consignee": null,
  "notify_party": null,
  "bol_number": "string or null",
  "booking_number": "string or null",
  "vessel_name": "string or null",
  "voyage_number": "string or null",
  "port_of_loading": "string or null",
  "port_of_discharge": "string or null",
  "place_of_delivery": "string or null",
  "eta": "YYYY-MM-DD or null",
  "ata": "YYYY-MM-DD or null",
  "container_numbers": ["string"],
  "cargo_description": "string or null",
  "package_count": 0,
  "gross_weight": 0,
  "weight_unit": "kg or lbs",
  "volume": 0,
  "volume_unit": "CBM or CFT",
  "freight_terms": "prepaid or collect",
  "charges": [{"charge_type": "string", "amount": 0, "currency": "string or null"}],
  "total_charges": 0,
  "currency": "USD",
  "free_time_days": 0,
  "last_free_day": "YYYY-MM-DD or null",
  "documents_required": ["string"],
  "notes": "string or null"
}"""

AIR_WAYBILL_SCHEMA = """{
  "awb_number": "string (11-digit IATA format)",
  "awb_type": "master or house or null",
  "master_awb_number": "string or null",
  "issue_date": "YYYY-MM-DD or null",
  "airline_code": "string or null",
  "airline_name": "string or null",
  "shipper": {"name": "string", "address": "string or null", "city": "string or null", "state": "string or null", "country": "string or null", "postal_code": "string or null", "tax_id": "string or null", "contact_name": "string or null", "phone": "string or null", "email": "string or null"},
  "consignee": null,
  "issuing_agent": null,
  "airport_of_departure": "string or null",
  "airport_of_destination": "string or null",
  "routing": ["string"],
  "flight_number": "string or null",
  "flight_date": "YYYY-MM-DD or null",
  "cargo_description": "string or null",
  "pieces": 0,
  "gross_weight": 0,
  "chargeable_weight": 0,
  "weight_unit": "K or L",
  "dimensions": "string or null",
  "volume": 0,
  "rate_class": "string or null",
  "rate": 0,
  "freight_charges": 0,
  "declared_value_carriage": 0,
  "declared_value_customs": 0,
  "insurance_amount": 0,
  "other_charges": [{"charge_code": "string or null", "charge_type": "string", "amount": 0, "prepaid_or_collect": "PP or CC"}],
  "total_charges": 0,
  "payment_type": "PP or CC or null",
  "currency": "USD",
  "handling_info": "string or null",
  "sci": "string or null",
  "notes": "string or null"
}"""

DEBIT_CREDIT_NOTE_SCHEMA = """{
  "note_number": "string",
  "note_type": "debit or credit",
  "note_date": "YYYY-MM-DD or null",
  "original_invoice_number": "string or null",
  "original_invoice_date": "YYYY-MM-DD or null",
  "issuer": {"name": "string", "address": "string or null", "city": "string or null", "state": "string or null", "country": "string or null", "postal_code": "string or null", "tax_id": "string or null", "contact_name": "string or null", "phone": "string or null", "email": "string or null"},
  "recipient": null,
  "currency": "USD",
  "reason": "string or null",
  "line_items": [{"description": "string", "original_amount": 0, "adjusted_amount": 0, "difference": 0, "quantity": 0, "unit": "string or null", "reason": "string or null"}],
  "subtotal": 0,
  "tax_amount": 0,
  "total_amount": 0,
  "notes": "string or null"
}"""

CUSTOMS_ENTRY_SCHEMA = """{
  "entry_number": "string (11-digit)",
  "entry_type": "string or null",
  "summary_date": "YYYY-MM-DD or null",
  "entry_date": "YYYY-MM-DD or null",
  "port_code": "string or null",
  "surety_number": "string or null",
  "bond_type": "string or null",
  "importing_carrier": "string or null",
  "mode_of_transport": "string or null",
  "country_of_origin": "string or null",
  "exporting_country": "string or null",
  "import_date": "YYYY-MM-DD or null",
  "importer_number": "string or null",
  "importer_name": "string or null",
  "consignee_number": "string or null",
  "consignee_name": "string or null",
  "manufacturer_id": "string or null",
  "bol_or_awb": "string or null",
  "line_items": [{"line_number": 0, "hts_number": "string (10-digit HTS)", "description": "string", "country_of_origin": "string or null", "quantity": 0, "unit": "string or null", "entered_value": 0, "duty_rate": 0, "duty_amount": 0, "ad_cvd_rate": "string or null", "ad_cvd_amount": 0}],
  "total_entered_value": 0,
  "total_duty": 0,
  "total_tax": 0,
  "total_other": 0,
  "total_amount": 0,
  "notes": "string or null"
}"""

PROOF_OF_DELIVERY_SCHEMA = """{
  "pod_number": "string or null",
  "delivery_date": "YYYY-MM-DD or null",
  "delivery_time": "HH:MM or null",
  "carrier_name": "string or null",
  "driver_name": "string or null",
  "shipper": {"name": "string", "address": "string or null", "city": "string or null", "state": "string or null", "country": "string or null", "postal_code": "string or null", "tax_id": "string or null", "contact_name": "string or null", "phone": "string or null", "email": "string or null"},
  "consignee": null,
  "delivery_address": "string or null",
  "bol_number": "string or null",
  "order_number": "string or null",
  "tracking_number": "string or null",
  "items": [{"description": "string", "quantity_expected": 0, "quantity_delivered": 0, "unit": "string or null", "condition": "string or null", "notes": "string or null"}],
  "total_packages": 0,
  "total_weight": 0,
  "weight_unit": "kg or lbs",
  "receiver_name": "string or null",
  "receiver_signature": false,
  "condition": "good|damaged|partial or null",
  "condition_notes": "string or null",
  "has_photo": false,
  "gps_coordinates": "string or null",
  "notes": "string or null"
}"""

CERTIFICATE_OF_ORIGIN_SCHEMA = """{
  "certificate_number": "string or null",
  "issue_date": "YYYY-MM-DD or null",
  "certificate_type": "General|Form A|EUR.1|USMCA or null",
  "exporter": {"name": "string", "address": "string or null", "city": "string or null", "state": "string or null", "country": "string or null", "postal_code": "string or null", "tax_id": "string or null", "contact_name": "string or null", "phone": "string or null", "email": "string or null"},
  "producer": null,
  "importer": null,
  "country_of_origin": "string",
  "country_of_destination": "string or null",
  "transport_details": "string or null",
  "invoice_number": "string or null",
  "items": [{"description": "string", "hs_code": "string or null", "quantity": 0, "unit": "string or null", "origin_criterion": "string or null", "country_of_origin": "string or null"}],
  "origin_criterion": "string or null",
  "blanket_period_start": "YYYY-MM-DD or null",
  "blanket_period_end": "YYYY-MM-DD or null",
  "issuing_authority": "string or null",
  "certifier_name": "string or null",
  "certification_date": "YYYY-MM-DD or null",
  "notes": "string or null"
}"""

# Registry mapping DocumentType to JSON schema template
_SCHEMA_REGISTRY: dict[DocumentType, str] = {
    DocumentType.FREIGHT_INVOICE: FREIGHT_INVOICE_SCHEMA,
    DocumentType.BILL_OF_LADING: BOL_SCHEMA,
    DocumentType.COMMERCIAL_INVOICE: COMMERCIAL_INVOICE_SCHEMA,
    DocumentType.PURCHASE_ORDER: PURCHASE_ORDER_SCHEMA,
    DocumentType.PACKING_LIST: PACKING_LIST_SCHEMA,
    DocumentType.ARRIVAL_NOTICE: ARRIVAL_NOTICE_SCHEMA,
    DocumentType.AIR_WAYBILL: AIR_WAYBILL_SCHEMA,
    DocumentType.DEBIT_CREDIT_NOTE: DEBIT_CREDIT_NOTE_SCHEMA,
    DocumentType.CUSTOMS_ENTRY: CUSTOMS_ENTRY_SCHEMA,
    DocumentType.PROOF_OF_DELIVERY: PROOF_OF_DELIVERY_SCHEMA,
    DocumentType.CERTIFICATE_OF_ORIGIN: CERTIFICATE_OF_ORIGIN_SCHEMA,
}


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
    return _SCHEMA_REGISTRY.get(doc_type, FREIGHT_INVOICE_SCHEMA)


def _validate_extraction(doc_type: DocumentType, data: dict) -> dict:
    """Validate extracted data against the Pydantic model for this type."""
    model_cls = EXTRACTION_MODEL_REGISTRY.get(doc_type)
    if model_cls is None:
        # Fallback to freight invoice for unknown types
        validated = FreightInvoiceExtraction.model_validate(data)
    else:
        validated = model_cls.model_validate(data)
    return validated.model_dump(mode="json")


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
        return _validate_extraction(doc_type, result)

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
        return _validate_extraction(doc_type, result)

    # Legacy method for backward compatibility with Phase 1 tests
    async def extract_freight_invoice(
        self, document_text: str
    ) -> FreightInvoiceExtraction:
        """Extract structured freight invoice data from document text."""
        result = await self.extract(
            doc_type=DocumentType.FREIGHT_INVOICE, text=document_text
        )
        return FreightInvoiceExtraction.model_validate(result)
