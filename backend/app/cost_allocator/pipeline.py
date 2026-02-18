"""
Cost allocation pipeline.

Takes a freight invoice extraction and allocates each line item to project codes,
cost centers, and GL accounts using Claude with business rules.
"""

import json
import logging
import time
from dataclasses import dataclass, field

import anthropic

from app.config import Settings

logger = logging.getLogger("gamma.cost_allocator.pipeline")

ALLOCATION_SYSTEM_PROMPT_TEMPLATE = """You are a logistics cost allocation specialist. Given a document (freight invoice, commercial invoice, or customs entry) with line items and a set of business allocation rules, assign each line item to the correct project code, cost center, and GL account.

ALLOCATION RULES:
{rules}

For each line item in the document, provide:
- line_item_index: The zero-based index of the line item
- project_code: The project code to allocate to
- cost_center: The cost center
- gl_account: The GL account code
- confidence: A float from 0.0 to 1.0 indicating how confident you are in this allocation
- reasoning: A brief explanation (1-2 sentences) of why this allocation was chosen

Matching guidelines:
- Match line item descriptions against the keywords in each rule
- If a line item clearly matches a rule, use that rule's codes with high confidence (0.9-1.0)
- If the match is partial or ambiguous, use your best judgment with moderate confidence (0.6-0.85)
- If no rule matches, use your domain knowledge of logistics accounting with lower confidence (0.3-0.6)
- Fuel surcharges should typically follow the primary freight charge they relate to
- For customs entries: duties go to 5220-DUTIES, MPF/HMF fees go to 5230-FEES
- For commercial invoices: goods value may be allocated by HS code or product category

Respond with a JSON array only, no additional text. Each element should have: line_item_index, project_code, cost_center, gl_account, confidence, reasoning."""


@dataclass
class AllocationLineItemResult:
    """Result for a single line item allocation."""

    line_item_index: int
    description: str
    amount: float
    project_code: str
    cost_center: str
    gl_account: str
    confidence: float
    reasoning: str


@dataclass
class AllocationResult:
    """Complete result of the cost allocation pipeline."""

    line_items: list[AllocationLineItemResult] = field(default_factory=list)
    model_used: str = ""
    processing_time_ms: int = 0
    total_amount: float = 0.0
    currency: str = "USD"


class CostAllocationPipeline:
    """Allocates freight invoice line items to cost codes using Claude."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.model = settings.claude_model
        self.confidence_threshold = settings.allocation_confidence_threshold

    async def allocate(
        self,
        extraction: dict,
        rules_text: str,
        doc_type: str = "freight_invoice",
    ) -> AllocationResult:
        """Run cost allocation on a document extraction.

        Args:
            extraction: The extraction dict (from Phase 2 pipeline).
            rules_text: Formatted business rules text for the prompt.
            doc_type: Document type string for dispatch (freight_invoice, commercial_invoice, customs_entry, debit_credit_note).

        Returns:
            AllocationResult with allocations for each line item.
        """
        start_time = time.monotonic()

        line_items = extraction.get("line_items", [])
        if not line_items:
            raise ValueError("No line items found in extraction")

        # Build the user message with document details
        invoice_summary = self._format_invoice(extraction, doc_type)

        # Build the system prompt with rules
        system_prompt = ALLOCATION_SYSTEM_PROMPT_TEMPLATE.format(rules=rules_text)

        logger.info("Allocating %d line items with Claude...", len(line_items))

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            temperature=0,
            system=system_prompt,
            messages=[{"role": "user", "content": invoice_summary}],
        )

        result_text = response.content[0].text.strip()

        # Strip markdown code blocks if present
        if "```" in result_text:
            parts = result_text.split("```")
            for part in parts:
                cleaned = part.strip().removeprefix("json").strip()
                if cleaned.startswith("["):
                    result_text = cleaned
                    break

        allocations_raw = json.loads(result_text)

        # Build results, merging Claude's allocations with original line item data
        result_items = []
        for alloc in allocations_raw:
            idx = alloc["line_item_index"]
            if idx < len(line_items):
                original = line_items[idx]
                result_items.append(AllocationLineItemResult(
                    line_item_index=idx,
                    description=original.get("description", ""),
                    amount=original.get("total", 0.0),
                    project_code=alloc.get("project_code", ""),
                    cost_center=alloc.get("cost_center", ""),
                    gl_account=alloc.get("gl_account", ""),
                    confidence=alloc.get("confidence", 0.0),
                    reasoning=alloc.get("reasoning", ""),
                ))

        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        total_amount = extraction.get("total_amount", 0.0)
        currency = extraction.get("currency", "USD")

        logger.info(
            "Allocation complete: %d items, %dms, total=%s %s",
            len(result_items), elapsed_ms, currency, total_amount,
        )

        return AllocationResult(
            line_items=result_items,
            model_used=self.model,
            processing_time_ms=elapsed_ms,
            total_amount=total_amount,
            currency=currency,
        )

    _FORMAT_DISPATCH: dict[str, str] = {
        "freight_invoice": "_format_freight_invoice",
        "commercial_invoice": "_format_commercial_invoice",
        "customs_entry": "_format_customs_entry",
        "debit_credit_note": "_format_debit_credit_note",
    }

    def _format_invoice(self, extraction: dict, doc_type: str = "freight_invoice") -> str:
        """Format an extraction as text for the Claude prompt.

        Dispatches to type-specific formatter based on doc_type parameter.
        """
        method_name = self._FORMAT_DISPATCH.get(doc_type, "_format_freight_invoice")
        return getattr(self, method_name)(extraction)

    def _format_freight_invoice(self, extraction: dict) -> str:
        """Format a freight invoice extraction."""
        lines = [
            f"Invoice Number: {extraction.get('invoice_number', 'N/A')}",
            f"Vendor: {extraction.get('vendor_name', 'N/A')}",
            f"Date: {extraction.get('invoice_date', 'N/A')}",
            f"Origin: {extraction.get('origin', 'N/A')} -> Destination: {extraction.get('destination', 'N/A')}",
            f"Currency: {extraction.get('currency', 'USD')}",
            "",
            "LINE ITEMS:",
        ]

        for i, item in enumerate(extraction.get("line_items", [])):
            lines.append(
                f"  [{i}] {item.get('description', 'N/A')} — "
                f"Qty: {item.get('quantity', 'N/A')} {item.get('unit', '')}, "
                f"Unit Price: {item.get('unit_price', 'N/A')}, "
                f"Total: {item.get('total', 'N/A')}"
            )

        lines.append(f"\nTotal Amount: {extraction.get('total_amount', 'N/A')}")
        return "\n".join(lines)

    def _format_commercial_invoice(self, extraction: dict) -> str:
        """Format a commercial invoice extraction."""
        seller = extraction.get("seller", {})
        buyer = extraction.get("buyer", {})
        seller_name = seller.get("name", "N/A") if isinstance(seller, dict) else "N/A"
        buyer_name = buyer.get("name", "N/A") if isinstance(buyer, dict) else "N/A"

        lines = [
            "Document Type: Commercial Invoice",
            f"Invoice Number: {extraction.get('invoice_number', 'N/A')}",
            f"Seller: {seller_name}",
            f"Buyer: {buyer_name}",
            f"Date: {extraction.get('invoice_date', 'N/A')}",
            f"Country of Origin: {extraction.get('country_of_origin', 'N/A')}",
            f"Incoterms: {extraction.get('incoterms', 'N/A')}",
            f"Currency: {extraction.get('currency', 'USD')}",
            "",
            "LINE ITEMS:",
        ]

        for i, item in enumerate(extraction.get("line_items", [])):
            hs_code = item.get("hs_code", "")
            hs_str = f" [HS: {hs_code}]" if hs_code else ""
            lines.append(
                f"  [{i}] {item.get('description', 'N/A')}{hs_str} — "
                f"Qty: {item.get('quantity', 'N/A')} {item.get('unit', '')}, "
                f"Unit Price: {item.get('unit_price', 'N/A')}, "
                f"Total: {item.get('total', 'N/A')}"
            )

        lines.append(f"\nTotal Amount: {extraction.get('total_amount', 'N/A')}")
        return "\n".join(lines)

    def _format_customs_entry(self, extraction: dict) -> str:
        """Format a CBP 7501 customs entry extraction."""
        lines = [
            "Document Type: CBP 7501 Customs Entry Summary",
            f"Entry Number: {extraction.get('entry_number', 'N/A')}",
            f"Importer: {extraction.get('importer_name', 'N/A')}",
            f"Summary Date: {extraction.get('summary_date', 'N/A')}",
            f"Port: {extraction.get('port_code', 'N/A')}",
            f"Country of Origin: {extraction.get('country_of_origin', 'N/A')}",
            "",
            "LINE ITEMS:",
        ]

        for i, item in enumerate(extraction.get("line_items", [])):
            lines.append(
                f"  [{i}] HTS {item.get('hts_number', 'N/A')}: {item.get('description', 'N/A')} — "
                f"Entered Value: {item.get('entered_value', 'N/A')}, "
                f"Duty Rate: {item.get('duty_rate', 'N/A')}, "
                f"Duty Amount: {item.get('duty_amount', 'N/A')}"
            )

        lines.append(f"\nTotal Entered Value: {extraction.get('total_entered_value', 'N/A')}")
        lines.append(f"Total Duty: {extraction.get('total_duty', 'N/A')}")
        lines.append(f"Total Other (MPF/HMF): {extraction.get('total_other', 'N/A')}")
        lines.append(f"Total Amount: {extraction.get('total_amount', 'N/A')}")
        return "\n".join(lines)

    def _format_debit_credit_note(self, extraction: dict) -> str:
        """Format a debit/credit note extraction."""
        lines = [
            f"Document Type: {(extraction.get('note_type') or 'N/A').title()} Note",
            f"Note Number: {extraction.get('note_number', 'N/A')}",
            f"Original Invoice: {extraction.get('original_invoice_number', 'N/A')}",
            f"Date: {extraction.get('note_date', 'N/A')}",
            f"Reason: {extraction.get('reason', 'N/A')}",
            f"Currency: {extraction.get('currency', 'USD')}",
            "",
            "LINE ITEMS:",
        ]

        for i, item in enumerate(extraction.get("line_items", [])):
            lines.append(
                f"  [{i}] {item.get('description', 'N/A')} — "
                f"Original: {item.get('original_amount', 'N/A')}, "
                f"Adjusted: {item.get('adjusted_amount', 'N/A')}, "
                f"Difference: {item.get('difference', 'N/A')}"
            )

        lines.append(f"\nTotal Amount: {extraction.get('total_amount', 'N/A')}")
        return "\n".join(lines)
