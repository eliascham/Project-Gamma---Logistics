"""
Validation accuracy evaluation.

Measures false positive / false negative rates of the deterministic validators
by running them against extraction dicts with known-correct annotations.
"""

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from app.schemas.extraction import DocumentType
from app.validator.service import ValidationService

logger = logging.getLogger("gamma.eval.validation")


@dataclass
class ValidationEvalResult:
    """Result for a single validated document."""
    filename: str
    document_type: str
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    details: list[dict] = field(default_factory=list)
    error: str | None = None


@dataclass
class ValidationEvalReport:
    """Complete validation evaluation report."""
    eval_id: str = ""
    results: list[ValidationEvalResult] = field(default_factory=list)
    overall_precision: float = 0.0
    overall_recall: float = 0.0
    overall_f1: float = 0.0
    per_rule_stats: dict[str, dict] = field(default_factory=dict)
    total_documents: int = 0
    elapsed_ms: int = 0

    def to_dict(self) -> dict:
        return {
            "eval_id": self.eval_id,
            "overall_precision": round(self.overall_precision, 4),
            "overall_recall": round(self.overall_recall, 4),
            "overall_f1": round(self.overall_f1, 4),
            "per_rule_stats": self.per_rule_stats,
            "total_documents": self.total_documents,
            "elapsed_ms": self.elapsed_ms,
            "results": [
                {
                    "filename": r.filename,
                    "document_type": r.document_type,
                    "true_positives": r.true_positives,
                    "false_positives": r.false_positives,
                    "false_negatives": r.false_negatives,
                    "details": r.details,
                    "error": r.error,
                }
                for r in self.results
            ],
        }


class ValidationEvaluator:
    """Runs validation eval against annotated ground truth documents."""

    def run(
        self, ground_truth_dir: str | None = None
    ) -> ValidationEvalReport:
        """Run validators on ground truth extractions and compare to annotations.

        Only processes *_expected.json files that contain a "validation_annotations"
        key. Files without this key are silently skipped.
        """
        start = time.monotonic()
        eval_id = str(uuid.uuid4())[:8]

        if ground_truth_dir is None:
            ground_truth_dir = str(Path(__file__).parent / "ground_truth")

        gt_path = Path(ground_truth_dir)
        if not gt_path.exists():
            raise FileNotFoundError(f"Ground truth directory not found: {ground_truth_dir}")

        expected_files = sorted(gt_path.glob("*_expected.json"))

        report = ValidationEvalReport(eval_id=eval_id)

        # Aggregate counters
        total_tp = 0
        total_fp = 0
        total_fn = 0
        # Per-rule tracking
        rule_stats: dict[str, dict[str, int]] = {}  # rule -> {tp, fp, fn}

        for expected_file in expected_files:
            with open(expected_file) as f:
                data = json.load(f)

            # Skip files without validation annotations
            annotations = data.get("validation_annotations")
            if annotations is None:
                continue

            doc_type_str = data.get("document_type", "freight_invoice")
            extraction = data.get("extraction", {})
            expected_issues = annotations.get("expected_issues", [])

            report.total_documents += 1

            try:
                # Convert doc_type string to enum
                try:
                    doc_type = DocumentType(doc_type_str)
                except ValueError:
                    doc_type = DocumentType.FREIGHT_INVOICE

                # Run validators
                result = ValidationService.validate(extraction, doc_type)

                # Build sets for comparison: (rule, field)
                actual_set = {(issue.rule, issue.field) for issue in result.issues}
                expected_set = {(ei["rule"], ei["field"]) for ei in expected_issues}

                tp = len(actual_set & expected_set)
                fp = len(actual_set - expected_set)
                fn = len(expected_set - actual_set)

                total_tp += tp
                total_fp += fp
                total_fn += fn

                # Per-rule stats
                all_rules = {r for r, _ in actual_set | expected_set}
                for rule in all_rules:
                    if rule not in rule_stats:
                        rule_stats[rule] = {"tp": 0, "fp": 0, "fn": 0}
                    rule_actual = {(r, f) for r, f in actual_set if r == rule}
                    rule_expected = {(r, f) for r, f in expected_set if r == rule}
                    rule_stats[rule]["tp"] += len(rule_actual & rule_expected)
                    rule_stats[rule]["fp"] += len(rule_actual - rule_expected)
                    rule_stats[rule]["fn"] += len(rule_expected - rule_actual)

                # Build details
                details = []
                for r, f in actual_set & expected_set:
                    details.append({"rule": r, "field": f, "result": "true_positive"})
                for r, f in actual_set - expected_set:
                    details.append({"rule": r, "field": f, "result": "false_positive"})
                for r, f in expected_set - actual_set:
                    details.append({"rule": r, "field": f, "result": "false_negative"})

                report.results.append(ValidationEvalResult(
                    filename=expected_file.name,
                    document_type=doc_type_str,
                    true_positives=tp,
                    false_positives=fp,
                    false_negatives=fn,
                    details=details,
                ))

            except Exception as e:
                logger.error("Validation eval failed for %s: %s", expected_file.name, e)
                report.results.append(ValidationEvalResult(
                    filename=expected_file.name,
                    document_type=doc_type_str,
                    error=str(e),
                ))

        # Compute aggregate metrics
        if total_tp + total_fp > 0:
            report.overall_precision = total_tp / (total_tp + total_fp)
        if total_tp + total_fn > 0:
            report.overall_recall = total_tp / (total_tp + total_fn)
        if report.overall_precision + report.overall_recall > 0:
            report.overall_f1 = (
                2 * report.overall_precision * report.overall_recall
                / (report.overall_precision + report.overall_recall)
            )

        # Per-rule precision/recall
        for rule, stats in rule_stats.items():
            rtp, rfp, rfn = stats["tp"], stats["fp"], stats["fn"]
            prec = rtp / (rtp + rfp) if rtp + rfp > 0 else 0.0
            rec = rtp / (rtp + rfn) if rtp + rfn > 0 else 0.0
            f1 = 2 * prec * rec / (prec + rec) if prec + rec > 0 else 0.0
            report.per_rule_stats[rule] = {
                "true_positives": rtp,
                "false_positives": rfp,
                "false_negatives": rfn,
                "precision": round(prec, 4),
                "recall": round(rec, 4),
                "f1": round(f1, 4),
            }

        report.elapsed_ms = int((time.monotonic() - start) * 1000)

        logger.info(
            "Validation eval complete: %d docs, precision=%.2f%%, recall=%.2f%%, F1=%.2f%%, %dms",
            report.total_documents, report.overall_precision * 100,
            report.overall_recall * 100, report.overall_f1 * 100, report.elapsed_ms,
        )

        return report
