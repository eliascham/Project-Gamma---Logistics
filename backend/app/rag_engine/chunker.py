"""
Text chunking utilities for RAG ingestion.

Splits text into overlapping chunks for embedding. Also converts structured
extraction data into natural language suitable for embedding and retrieval.
"""


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split text into overlapping chunks.

    Args:
        text: The text to chunk.
        chunk_size: Target size of each chunk in characters.
        overlap: Number of overlapping characters between chunks.

    Returns:
        List of text chunks.
    """
    if not text or not text.strip():
        return []

    text = text.strip()
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size

        # Try to break at a sentence or paragraph boundary
        if end < len(text):
            # Look for the last period, newline, or semicolon within the chunk
            for sep in ["\n\n", "\n", ". ", "; "]:
                last_break = text.rfind(sep, start + chunk_size // 2, end)
                if last_break > start:
                    end = last_break + len(sep)
                    break

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        start = end - overlap

    return chunks


def extraction_to_text(extraction: dict, doc_type: str) -> str:
    """Convert a structured extraction into natural language text for embedding.

    This is important because embeddings work better on natural language than
    on raw JSON. We produce a readable summary of the extracted data.
    """
    if doc_type == "freight_invoice":
        return _freight_invoice_to_text(extraction)
    elif doc_type == "bill_of_lading":
        return _bol_to_text(extraction)
    else:
        # Fallback: format as key-value pairs
        lines = []
        for key, value in extraction.items():
            if value is not None:
                lines.append(f"{key.replace('_', ' ').title()}: {value}")
        return "\n".join(lines)


def _freight_invoice_to_text(ext: dict) -> str:
    """Convert a freight invoice extraction to natural language."""
    lines = [
        f"Freight Invoice {ext.get('invoice_number', 'N/A')}",
        f"from {ext.get('vendor_name', 'unknown vendor')}",
        f"dated {ext.get('invoice_date', 'unknown date')}.",
    ]

    if ext.get("shipper_name"):
        lines.append(f"Shipper: {ext['shipper_name']}.")
    if ext.get("consignee_name"):
        lines.append(f"Consignee: {ext['consignee_name']}.")

    origin = ext.get("origin", "")
    dest = ext.get("destination", "")
    if origin or dest:
        lines.append(f"Route: {origin or 'N/A'} to {dest or 'N/A'}.")

    line_items = ext.get("line_items", [])
    if line_items:
        lines.append(f"The invoice has {len(line_items)} line items:")
        for item in line_items:
            desc = item.get("description", "")
            total = item.get("total", 0)
            qty = item.get("quantity", "")
            unit = item.get("unit", "")
            lines.append(
                f"- {desc}: {qty} {unit} at {item.get('unit_price', 'N/A')} each, "
                f"totaling {ext.get('currency', 'USD')} {total}."
            )

    total = ext.get("total_amount")
    if total is not None:
        lines.append(f"Total invoice amount: {ext.get('currency', 'USD')} {total}.")

    if ext.get("notes"):
        lines.append(f"Notes: {ext['notes']}")

    return " ".join(lines)


def _bol_to_text(ext: dict) -> str:
    """Convert a bill of lading extraction to natural language."""
    lines = [
        f"Bill of Lading {ext.get('bol_number', 'N/A')}",
        f"issued {ext.get('issue_date', 'unknown date')}.",
    ]

    if ext.get("carrier_name"):
        lines.append(f"Carrier: {ext['carrier_name']}.")
    if ext.get("vessel_name"):
        lines.append(f"Vessel: {ext['vessel_name']}.")

    shipper = ext.get("shipper")
    if shipper and isinstance(shipper, dict):
        lines.append(f"Shipper: {shipper.get('name', 'N/A')}.")
    consignee = ext.get("consignee")
    if consignee and isinstance(consignee, dict):
        lines.append(f"Consignee: {consignee.get('name', 'N/A')}.")

    origin = ext.get("origin", {})
    dest = ext.get("destination", {})
    if origin or dest:
        o_str = ", ".join(filter(None, [
            origin.get("port"), origin.get("city"), origin.get("country")
        ])) if isinstance(origin, dict) else str(origin)
        d_str = ", ".join(filter(None, [
            dest.get("port"), dest.get("city"), dest.get("country")
        ])) if isinstance(dest, dict) else str(dest)
        lines.append(f"Route: {o_str or 'N/A'} to {d_str or 'N/A'}.")

    if ext.get("cargo_description"):
        lines.append(f"Cargo: {ext['cargo_description']}.")
    if ext.get("gross_weight"):
        lines.append(f"Weight: {ext['gross_weight']} {ext.get('weight_unit', '')}.")
    if ext.get("container_numbers"):
        lines.append(f"Containers: {', '.join(ext['container_numbers'])}.")

    return " ".join(lines)
