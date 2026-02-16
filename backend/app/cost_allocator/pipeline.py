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

ALLOCATION_SYSTEM_PROMPT_TEMPLATE = """You are a logistics cost allocation specialist. Given a freight invoice with line items and a set of business allocation rules, assign each line item to the correct project code, cost center, and GL account.

ALLOCATION RULES:
{rules}

For each line item in the invoice, provide:
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
    ) -> AllocationResult:
        """Run cost allocation on a freight invoice extraction.

        Args:
            extraction: The freight invoice extraction dict (from Phase 2 pipeline).
            rules_text: Formatted business rules text for the prompt.

        Returns:
            AllocationResult with allocations for each line item.
        """
        start_time = time.monotonic()

        line_items = extraction.get("line_items", [])
        if not line_items:
            raise ValueError("No line items found in extraction")

        # Build the user message with invoice details
        invoice_summary = self._format_invoice(extraction)

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

    def _format_invoice(self, extraction: dict) -> str:
        """Format a freight invoice extraction as text for the Claude prompt."""
        lines = [
            f"Invoice Number: {extraction.get('invoice_number', 'N/A')}",
            f"Vendor: {extraction.get('vendor_name', 'N/A')}",
            f"Date: {extraction.get('invoice_date', 'N/A')}",
            f"Origin: {extraction.get('origin', 'N/A')} → Destination: {extraction.get('destination', 'N/A')}",
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
