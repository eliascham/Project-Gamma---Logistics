"""
Classification accuracy evaluation.

Runs each ground truth document through the classifier (Haiku) and measures
whether the document type is correctly identified.
"""

import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
import json

import anthropic

from app.config import Settings
from app.document_extractor.classifier import DocumentClassifier
from app.document_extractor.parser import DocumentParser
from app.schemas.extraction import DocumentType

logger = logging.getLogger("gamma.eval.classification")


@dataclass
class ClassificationResult:
    """Result for a single classified document."""
    filename: str
    expected_type: str
    predicted_type: str
    correct: bool
    error: str | None = None


@dataclass
class ClassificationEvalReport:
    """Complete classification evaluation report."""
    eval_id: str = ""
    results: list[ClassificationResult] = field(default_factory=list)
    accuracy: float = 0.0
    per_type_accuracy: dict[str, float] = field(default_factory=dict)
    confusion_matrix: dict[str, dict[str, int]] = field(default_factory=dict)
    total_documents: int = 0
    successful_documents: int = 0
    elapsed_ms: int = 0
    model_used: str = ""

    def to_dict(self) -> dict:
        return {
            "eval_id": self.eval_id,
            "accuracy": round(self.accuracy, 4),
            "per_type_accuracy": {k: round(v, 4) for k, v in self.per_type_accuracy.items()},
            "confusion_matrix": self.confusion_matrix,
            "total_documents": self.total_documents,
            "successful_documents": self.successful_documents,
            "elapsed_ms": self.elapsed_ms,
            "model_used": self.model_used,
            "results": [
                {
                    "filename": r.filename,
                    "expected_type": r.expected_type,
                    "predicted_type": r.predicted_type,
                    "correct": r.correct,
                    "error": r.error,
                }
                for r in self.results
            ],
        }


class ClassificationEvaluator:
    """Runs classification evaluation against ground truth documents."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.classifier = DocumentClassifier(
            client=self.client,
            model=settings.claude_haiku_model,
        )
        self.parser = DocumentParser()

    async def run(
        self, ground_truth_dir: str | None = None
    ) -> ClassificationEvalReport:
        """Run classification on all ground truth documents.

        Uses the same *_expected.json discovery pattern as ExtractionEvaluator.
        Only processes files that have a paired source document (CSV/PDF/image).
        """
        start = time.monotonic()
        eval_id = str(uuid.uuid4())[:8]

        if ground_truth_dir is None:
            ground_truth_dir = str(Path(__file__).parent / "ground_truth")

        gt_path = Path(ground_truth_dir)
        if not gt_path.exists():
            raise FileNotFoundError(f"Ground truth directory not found: {ground_truth_dir}")

        expected_files = sorted(gt_path.glob("*_expected.json"))
        if not expected_files:
            raise ValueError(f"No *_expected.json files found in {ground_truth_dir}")

        report = ClassificationEvalReport(
            eval_id=eval_id,
            model_used=self.settings.claude_haiku_model,
        )

        # Track per-type counts for accuracy
        type_correct: dict[str, int] = {}
        type_total: dict[str, int] = {}
        # Confusion matrix: confusion[expected][predicted] = count
        confusion: dict[str, dict[str, int]] = {}

        for expected_file in expected_files:
            # Load expected data
            with open(expected_file) as f:
                expected_data = json.load(f)

            # Skip validation-only files (no paired source doc)
            if "validation_annotations" in expected_data:
                continue

            doc_type_str = expected_data.get("document_type", "unknown")
            base_name = expected_file.stem.replace("_expected", "")

            # Find paired source document
            doc_file = None
            for ext in [".csv", ".pdf", ".png", ".jpg", ".txt"]:
                candidate = gt_path / f"{base_name}{ext}"
                if candidate.exists():
                    doc_file = candidate
                    break

            if doc_file is None:
                continue  # Skip files without source docs

            report.total_documents += 1
            type_total[doc_type_str] = type_total.get(doc_type_str, 0) + 1

            try:
                # Parse document
                file_type = doc_file.suffix.lstrip(".")
                mime_map = {
                    "csv": "text/csv", "pdf": "application/pdf",
                    "png": "image/png", "jpg": "image/jpeg", "txt": "text/plain",
                }
                mime_type = mime_map.get(file_type, "application/octet-stream")
                parsed = self.parser.parse(str(doc_file), file_type, mime_type)

                # Classify
                predicted_type = await self.classifier.classify(
                    text=parsed.text,
                    images=parsed.images or None,
                )

                predicted_str = predicted_type.value if isinstance(predicted_type, DocumentType) else str(predicted_type)
                correct = predicted_str == doc_type_str

                if correct:
                    type_correct[doc_type_str] = type_correct.get(doc_type_str, 0) + 1

                # Update confusion matrix
                if doc_type_str not in confusion:
                    confusion[doc_type_str] = {}
                confusion[doc_type_str][predicted_str] = confusion[doc_type_str].get(predicted_str, 0) + 1

                report.results.append(ClassificationResult(
                    filename=doc_file.name,
                    expected_type=doc_type_str,
                    predicted_type=predicted_str,
                    correct=correct,
                ))
                report.successful_documents += 1

            except Exception as e:
                logger.error("Classification eval failed for %s: %s", doc_file.name, e)
                report.results.append(ClassificationResult(
                    filename=doc_file.name,
                    expected_type=doc_type_str,
                    predicted_type="error",
                    correct=False,
                    error=str(e),
                ))

        # Compute metrics
        if report.successful_documents > 0:
            correct_count = sum(1 for r in report.results if r.correct)
            report.accuracy = correct_count / report.successful_documents

        for doc_type, total in type_total.items():
            correct = type_correct.get(doc_type, 0)
            report.per_type_accuracy[doc_type] = correct / total if total > 0 else 0.0

        report.confusion_matrix = confusion
        report.elapsed_ms = int((time.monotonic() - start) * 1000)

        logger.info(
            "Classification eval complete: %d/%d docs, accuracy=%.2f%%, %dms",
            report.successful_documents, report.total_documents,
            report.accuracy * 100, report.elapsed_ms,
        )

        return report
