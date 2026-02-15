"""
Document classifier using Claude Haiku for fast, cheap pre-screening.

Classifies logistics documents into types (freight invoice, BOL, etc.)
before running the full extraction pipeline with Sonnet.
"""

import json
import logging

import anthropic

from app.schemas.extraction import DocumentType

logger = logging.getLogger("gamma.classifier")

CLASSIFICATION_PROMPT = """Classify this logistics document into one of the following types:
- freight_invoice: A freight or shipping invoice with charges, line items, and payment amounts
- bill_of_lading: A Bill of Lading (BOL/B/L) with shipping details, cargo info, and carrier information
- unknown: Cannot determine the document type

Respond with ONLY a JSON object: {"document_type": "<type>"}"""


class DocumentClassifier:
    """Classifies document type using Claude Haiku."""

    def __init__(self, client: anthropic.AsyncAnthropic, model: str):
        self.client = client
        self.model = model

    async def classify(
        self, text: str = "", images: list[dict] | None = None
    ) -> DocumentType:
        """Classify a document based on its text and/or images.

        Args:
            text: Extracted text from the document.
            images: List of {"base64": str, "media_type": str} dicts for vision.

        Returns:
            DocumentType enum value.
        """
        content = self._build_content(text, images)

        if not content:
            logger.warning("No content to classify")
            return DocumentType.UNKNOWN

        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=100,
                system=CLASSIFICATION_PROMPT,
                messages=[{"role": "user", "content": content}],
            )

            result_text = response.content[0].text.strip()

            # Strip markdown code blocks if present
            if "```" in result_text:
                # Extract content between ```json ... ``` or ``` ... ```
                parts = result_text.split("```")
                for part in parts:
                    cleaned = part.strip().removeprefix("json").strip()
                    if cleaned.startswith("{"):
                        result_text = cleaned
                        break

            # Parse JSON response
            if result_text.startswith("{"):
                data = json.loads(result_text)
                doc_type_str = data.get("document_type", "unknown")
            else:
                doc_type_str = result_text.lower()

            # Map to enum
            try:
                return DocumentType(doc_type_str)
            except ValueError:
                logger.warning("Unknown document type from classifier: %s", doc_type_str)
                return DocumentType.UNKNOWN

        except Exception as e:
            logger.error("Classification failed: %s", e)
            return DocumentType.UNKNOWN

    def _build_content(
        self, text: str, images: list[dict] | None
    ) -> list[dict]:
        """Build the message content array for Claude API."""
        content: list[dict] = []

        # Add images first (vision)
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

        # Add text
        if text.strip():
            # Truncate for classification — only need first ~2000 chars
            preview = text[:2000]
            content.append({"type": "text", "text": f"Document content:\n\n{preview}"})

        return content
