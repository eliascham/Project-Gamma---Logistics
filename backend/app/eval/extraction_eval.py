"""
Extraction evaluation harness.

Runs sample documents through the extraction pipeline and compares
results against ground truth to measure accuracy.
"""

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from app.config import Settings
from app.document_extractor.pipeline import ExtractionPipeline
from app.eval.metrics import ExtractionScore, compute_extraction_score
from app.schemas.extraction import DocumentType

logger = logging.getLogger("gamma.eval")

# Fields to evaluate per document type
FREIGHT_INVOICE_FIELDS = [
    "invoice_number", "invoice_date", "vendor_name",
    "shipper_name", "consignee_name", "origin", "destination",
    "currency", "subtotal", "tax_amount", "total_amount",
]

BOL_FIELDS = [
    "bol_number", "issue_date", "carrier_name", "carrier_scac",
    "vessel_name", "voyage_number", "cargo_description",
    "package_count", "gross_weight", "weight_unit",
    "volume", "volume_unit", "freight_charges", "freight_payment_type",
]


@dataclass
class EvalDocumentResult:
    """Result for a single evaluated document."""

    filename: str
    document_type: str
    pass1_score: ExtractionScore | None = None
    pass2_score: ExtractionScore | None = None
    error: str | None = None


@dataclass
class EvalReport:
    """Complete evaluation report."""

    eval_id: str = ""
    document_results: list[EvalDocumentResult] = field(default_factory=list)
    overall_pass1_accuracy: float = 0.0
    overall_pass2_accuracy: float = 0.0
    model_used: str = ""
    haiku_model: str = ""
    total_documents: int = 0
    successful_documents: int = 0
    elapsed_ms: int = 0

    def to_dict(self) -> dict:
        return {
            "eval_id": self.eval_id,
            "overall_pass1_accuracy": round(self.overall_pass1_accuracy, 4),
            "overall_pass2_accuracy": round(self.overall_pass2_accuracy, 4),
            "model_used": self.model_used,
            "haiku_model": self.haiku_model,
            "total_documents": self.total_documents,
            "successful_documents": self.successful_documents,
            "elapsed_ms": self.elapsed_ms,
            "documents": [
                {
                    "filename": dr.filename,
                    "document_type": dr.document_type,
                    "pass1_score": dr.pass1_score.to_dict() if dr.pass1_score else None,
                    "pass2_score": dr.pass2_score.to_dict() if dr.pass2_score else None,
                    "error": dr.error,
                }
                for dr in self.document_results
            ],
        }


def _get_fields_for_type(doc_type: str) -> tuple[list[str], str | None]:
    """Get the scalar fields and line items field for a document type."""
    if doc_type == "bill_of_lading":
        return BOL_FIELDS, None  # BOLs don't have line_items
    return FREIGHT_INVOICE_FIELDS, "line_items"


class ExtractionEvaluator:
    """Runs extraction evaluation against ground truth documents."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.pipeline = ExtractionPipeline(settings)

    async def run(
        self,
        ground_truth_dir: str | None = None,
    ) -> EvalReport:
        """Run evaluation on all ground truth documents.

        Args:
            ground_truth_dir: Path to directory with document files and _expected.json files.
                Defaults to the built-in ground_truth directory.

        Returns:
            EvalReport with per-document and overall scores.
        """
        start_time = time.monotonic()
        eval_id = str(uuid.uuid4())[:8]

        if ground_truth_dir is None:
            ground_truth_dir = str(Path(__file__).parent / "ground_truth")

        gt_path = Path(ground_truth_dir)
        if not gt_path.exists():
            raise FileNotFoundError(f"Ground truth directory not found: {ground_truth_dir}")

        # Find all expected.json files
        expected_files = sorted(gt_path.glob("*_expected.json"))

        if not expected_files:
            raise ValueError(f"No *_expected.json files found in {ground_truth_dir}")

        report = EvalReport(
            eval_id=eval_id,
            model_used=self.settings.claude_model,
            haiku_model=self.settings.claude_haiku_model,
            total_documents=len(expected_files),
        )

        pass1_scores = []
        pass2_scores = []

        for expected_file in expected_files:
            # Derive document filename: freight_invoice_01_expected.json -> freight_invoice_01.csv
            base_name = expected_file.stem.replace("_expected", "")

            # Find the matching document file
            doc_file = None
            for ext in [".csv", ".pdf", ".png", ".jpg", ".txt"]:
                candidate = gt_path / f"{base_name}{ext}"
                if candidate.exists():
                    doc_file = candidate
                    break

            if doc_file is None:
                report.document_results.append(EvalDocumentResult(
                    filename=base_name,
                    document_type="unknown",
                    error=f"Document file not found for {expected_file.name}",
                ))
                continue

            # Load expected output
            with open(expected_file) as f:
                expected_data = json.load(f)

            doc_type_str = expected_data.get("document_type", "freight_invoice")
            expected_extraction = expected_data.get("extraction", {})

            # Determine file type from extension
            file_type = doc_file.suffix.lstrip(".")
            mime_map = {
                "csv": "text/csv", "pdf": "application/pdf",
                "png": "image/png", "jpg": "image/jpeg",
            }
            mime_type = mime_map.get(file_type, "application/octet-stream")

            try:
                # Force the known document type so eval measures extraction
                # accuracy, not classification accuracy
                try:
                    force_type = DocumentType(doc_type_str)
                except ValueError:
                    force_type = None

                # Run extraction pipeline
                result = await self.pipeline.run(
                    file_path=str(doc_file),
                    file_type=file_type,
                    mime_type=mime_type,
                    force_doc_type=force_type,
                )

                # Score both passes
                scalar_fields, line_items_field = _get_fields_for_type(doc_type_str)

                pass1_score = compute_extraction_score(
                    expected_extraction, result.raw_extraction,
                    scalar_fields, line_items_field,
                )
                pass2_score = compute_extraction_score(
                    expected_extraction, result.refined_extraction,
                    scalar_fields, line_items_field,
                )

                pass1_scores.append(pass1_score.overall_accuracy)
                pass2_scores.append(pass2_score.overall_accuracy)
                report.successful_documents += 1

                report.document_results.append(EvalDocumentResult(
                    filename=doc_file.name,
                    document_type=doc_type_str,
                    pass1_score=pass1_score,
                    pass2_score=pass2_score,
                ))

            except Exception as e:
                logger.error("Eval failed for %s: %s", doc_file.name, e)
                report.document_results.append(EvalDocumentResult(
                    filename=doc_file.name,
                    document_type=doc_type_str,
                    error=str(e),
                ))

        # Compute overall averages
        if pass1_scores:
            report.overall_pass1_accuracy = sum(pass1_scores) / len(pass1_scores)
        if pass2_scores:
            report.overall_pass2_accuracy = sum(pass2_scores) / len(pass2_scores)

        report.elapsed_ms = int((time.monotonic() - start_time) * 1000)

        logger.info(
            "Eval complete: %d/%d docs, pass1=%.2f%%, pass2=%.2f%%, %dms",
            report.successful_documents,
            report.total_documents,
            report.overall_pass1_accuracy * 100,
            report.overall_pass2_accuracy * 100,
            report.elapsed_ms,
        )

        return report
