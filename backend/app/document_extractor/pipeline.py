"""
2-pass extraction pipeline for logistics documents.

Flow:
  1. Parse document → text + images
  2. Classify document type (Haiku)
  3. Pass 1: Extract raw data (Sonnet)
  4. Pass 2: Self-review, refine, and score confidence (Sonnet)
  5. Deterministic validation
  6. Compute blended field-level confidence
  7. Return final extraction + confidence + validation
"""

import logging
import time
from dataclasses import dataclass, field

import anthropic

from app.config import Settings
from app.document_extractor.classifier import DocumentClassifier
from app.document_extractor.parser import DocumentParser, ParsedDocument
from app.schemas.extraction import DocumentType
from app.schemas.validation import ValidationResult
from app.services.claude_service import ClaudeService
from app.validator.confidence import (
    blend_confidences,
    compute_agreement_confidence,
    compute_overall_confidence,
)
from app.validator.service import ValidationService

logger = logging.getLogger("gamma.pipeline")


@dataclass
class ExtractionResult:
    """Complete result of the extraction pipeline."""

    document_type: DocumentType
    raw_extraction: dict  # Pass 1 output
    refined_extraction: dict  # Pass 2 output (final)
    model_used: str
    haiku_model: str
    processing_time_ms: int = 0
    parsed_document: ParsedDocument | None = None
    metadata: dict = field(default_factory=dict)
    field_confidences: dict[str, float] = field(default_factory=dict)
    overall_confidence: float = 0.0
    validation: ValidationResult | None = None


class ExtractionPipeline:
    """Orchestrates the full document extraction flow."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.parser = DocumentParser()
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.classifier = DocumentClassifier(
            client=self.client, model=settings.claude_haiku_model
        )
        self.claude_service = ClaudeService(settings)

    async def run(
        self,
        file_path: str,
        file_type: str,
        mime_type: str,
        skip_classification: bool = False,
        force_doc_type: DocumentType | None = None,
    ) -> ExtractionResult:
        """Run the full extraction pipeline on a document.

        Args:
            file_path: Path to document file on disk.
            file_type: File extension (e.g., "pdf", "png", "csv").
            mime_type: MIME type of the file.
            skip_classification: If True, skip Haiku classification step.
            force_doc_type: Force a specific document type (skips classification).

        Returns:
            ExtractionResult with both pass 1 and pass 2 outputs.
        """
        start_time = time.monotonic()

        # Step 1: Parse
        logger.info("Parsing document: %s (type=%s)", file_path, file_type)
        parsed = await self.parser.parse(file_path, file_type, mime_type)

        if not parsed.has_text and not parsed.has_images:
            raise ValueError("Document has no extractable content (no text or images)")

        # Step 2: Classify
        if force_doc_type:
            doc_type = force_doc_type
            logger.info("Using forced document type: %s", doc_type.value)
        elif skip_classification:
            doc_type = DocumentType.FREIGHT_INVOICE
            logger.info("Skipping classification, defaulting to freight_invoice")
        else:
            logger.info("Classifying document with Haiku...")
            doc_type = await self.classifier.classify(
                text=parsed.text, images=parsed.images or None
            )
            logger.info("Classified as: %s", doc_type.value)

        # Step 3: Pass 1 — Extract
        logger.info("Pass 1: Extracting structured data...")
        raw_extraction = await self.claude_service.extract(
            doc_type=doc_type,
            text=parsed.text,
            images=parsed.images or None,
        )
        logger.info("Pass 1 complete")

        # Step 4: Pass 2 — Review, refine, and score confidence
        logger.info("Pass 2: Reviewing, refining, and scoring confidence...")
        refined_extraction, claude_confidences = (
            await self.claude_service.review_extraction(
                doc_type=doc_type,
                raw_extraction=raw_extraction,
                text=parsed.text,
                images=parsed.images or None,
            )
        )
        logger.info("Pass 2 complete")

        # Step 5: Compute blended field-level confidence
        agreement_scores = compute_agreement_confidence(
            raw_extraction, refined_extraction
        )
        field_confidences = blend_confidences(agreement_scores, claude_confidences)
        overall_confidence = compute_overall_confidence(field_confidences)
        logger.info(
            "Confidence: overall=%.3f, fields=%d, claude_reported=%s",
            overall_confidence,
            len(field_confidences),
            claude_confidences is not None,
        )

        # Step 6: Deterministic validation
        validation = ValidationService.validate(refined_extraction, doc_type)
        logger.info(
            "Validation: passed=%s, errors=%d, warnings=%d",
            validation.passed,
            validation.error_count,
            validation.warning_count,
        )

        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        return ExtractionResult(
            document_type=doc_type,
            raw_extraction=raw_extraction,
            refined_extraction=refined_extraction,
            model_used=self.settings.claude_model,
            haiku_model=self.settings.claude_haiku_model,
            processing_time_ms=elapsed_ms,
            parsed_document=parsed,
            metadata={
                "page_count": parsed.page_count,
                "vision_used": parsed.is_vision_required,
                "text_chars": len(parsed.text),
                "image_count": len(parsed.images),
                **parsed.metadata,
            },
            field_confidences=field_confidences,
            overall_confidence=overall_confidence,
            validation=validation,
        )
