"""
Confidence calibration evaluation.

Measures whether the confidence scoring system is well-calibrated:
when the model reports 0.9 confidence, is the field correct ~90% of the time?

Metrics:
- ECE (Expected Calibration Error): weighted avg of |bin_accuracy - bin_midpoint|
- Brier Score: mean((confidence - correctness)^2)
"""

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from app.config import Settings
from app.document_extractor.pipeline import ExtractionPipeline
from app.eval.extraction_eval import _get_fields_for_type
from app.eval.metrics import compute_field_accuracy
from app.schemas.extraction import DocumentType

logger = logging.getLogger("gamma.eval.confidence")


@dataclass
class CalibrationBin:
    """A single calibration bin."""
    bin_lower: float
    bin_upper: float
    field_count: int = 0
    correct_count: int = 0
    accuracy: float = 0.0
    calibration_error: float = 0.0

    def to_dict(self) -> dict:
        return {
            "bin_range": f"{self.bin_lower:.1f}-{self.bin_upper:.1f}",
            "field_count": self.field_count,
            "correct_count": self.correct_count,
            "accuracy": round(self.accuracy, 4),
            "calibration_error": round(self.calibration_error, 4),
        }


@dataclass
class ConfidenceCalibrationReport:
    """Complete confidence calibration report."""
    eval_id: str = ""
    bins: list[CalibrationBin] = field(default_factory=list)
    ece: float = 0.0
    brier_score: float = 0.0
    total_fields: int = 0
    model_used: str = ""
    elapsed_ms: int = 0

    def to_dict(self) -> dict:
        return {
            "eval_id": self.eval_id,
            "ece": round(self.ece, 4),
            "brier_score": round(self.brier_score, 4),
            "total_fields": self.total_fields,
            "model_used": self.model_used,
            "elapsed_ms": self.elapsed_ms,
            "bins": [b.to_dict() for b in self.bins],
        }


class ConfidenceCalibrationEvaluator:
    """Measures whether confidence scores are well-calibrated."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.pipeline = ExtractionPipeline(settings)

    async def run(
        self,
        ground_truth_dir: str | None = None,
        num_bins: int = 5,
    ) -> ConfidenceCalibrationReport:
        """Run pipeline on ground truth docs and measure confidence calibration.

        For each document:
          1. Run full pipeline -> ExtractionResult (has field_confidences)
          2. For each eval field, get confidence score + check correctness vs ground truth
          3. Collect (confidence, is_correct) pairs

        Then bin into equal-width buckets and compute ECE + Brier score.
        """
        start = time.monotonic()
        eval_id = str(uuid.uuid4())[:8]

        if ground_truth_dir is None:
            ground_truth_dir = str(Path(__file__).parent / "ground_truth")

        gt_path = Path(ground_truth_dir)
        if not gt_path.exists():
            raise FileNotFoundError(f"Ground truth directory not found: {ground_truth_dir}")

        expected_files = sorted(gt_path.glob("*_expected.json"))

        # Collect all (confidence, correctness) pairs
        pairs: list[tuple[float, float]] = []

        for expected_file in expected_files:
            with open(expected_file) as f:
                expected_data = json.load(f)

            # Skip validation-only files
            if "validation_annotations" in expected_data:
                continue

            doc_type_str = expected_data.get("document_type", "freight_invoice")
            expected_extraction = expected_data.get("extraction", {})
            base_name = expected_file.stem.replace("_expected", "")

            # Find paired source document
            doc_file = None
            for ext in [".csv", ".pdf", ".png", ".jpg", ".txt"]:
                candidate = gt_path / f"{base_name}{ext}"
                if candidate.exists():
                    doc_file = candidate
                    break

            if doc_file is None:
                continue

            try:
                file_type = doc_file.suffix.lstrip(".")
                mime_map = {
                    "csv": "text/csv", "pdf": "application/pdf",
                    "png": "image/png", "jpg": "image/jpeg", "txt": "text/plain",
                }
                mime_type = mime_map.get(file_type, "application/octet-stream")

                # Force doc type so we measure extraction, not classification
                try:
                    force_type = DocumentType(doc_type_str)
                except ValueError:
                    force_type = None

                result = await self.pipeline.run(
                    file_path=str(doc_file),
                    file_type=file_type,
                    mime_type=mime_type,
                    force_doc_type=force_type,
                )

                # Get eval fields for this type
                scalar_fields, _ = _get_fields_for_type(doc_type_str)

                # For each scalar field, pair confidence with correctness
                for field_name in scalar_fields:
                    # Get confidence: try field_confidences first, fall back to overall
                    confidence = result.field_confidences.get(
                        field_name,
                        result.overall_confidence,
                    )

                    # Check correctness against ground truth
                    score = compute_field_accuracy(
                        expected_extraction, result.refined_extraction, field_name
                    )
                    correctness = 1.0 if score.match else 0.0

                    pairs.append((confidence, correctness))

            except Exception as e:
                logger.error("Confidence eval failed for %s: %s", doc_file.name if doc_file else base_name, e)

        # Build bins
        bin_width = 1.0 / num_bins
        bins: list[CalibrationBin] = []

        for i in range(num_bins):
            lower = i * bin_width
            upper = (i + 1) * bin_width
            bin_pairs = [
                (c, corr) for c, corr in pairs
                if lower <= c < upper or (i == num_bins - 1 and c == upper)
            ]

            b = CalibrationBin(bin_lower=lower, bin_upper=upper)
            b.field_count = len(bin_pairs)
            if bin_pairs:
                b.correct_count = sum(1 for _, corr in bin_pairs if corr == 1.0)
                b.accuracy = b.correct_count / b.field_count
                bin_midpoint = (lower + upper) / 2
                b.calibration_error = abs(b.accuracy - bin_midpoint)
            bins.append(b)

        # Compute ECE (weighted by bin size)
        total_fields = len(pairs)
        ece = 0.0
        if total_fields > 0:
            for b in bins:
                ece += (b.field_count / total_fields) * b.calibration_error

        # Compute Brier score
        brier = 0.0
        if total_fields > 0:
            brier = sum((c - corr) ** 2 for c, corr in pairs) / total_fields

        report = ConfidenceCalibrationReport(
            eval_id=eval_id,
            bins=bins,
            ece=ece,
            brier_score=brier,
            total_fields=total_fields,
            model_used=self.settings.claude_model,
            elapsed_ms=int((time.monotonic() - start) * 1000),
        )

        logger.info(
            "Confidence calibration complete: %d fields, ECE=%.4f, Brier=%.4f, %dms",
            total_fields, ece, brier, report.elapsed_ms,
        )

        return report
