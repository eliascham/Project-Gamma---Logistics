"""
Regression baseline system.

Stores a snapshot of best-known eval scores as a JSON file.
Future eval runs can compare against the baseline to detect regressions.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("gamma.eval.baseline")

BASELINE_FILE = Path(__file__).parent / "baseline.json"


@dataclass
class RegressionResult:
    """Comparison of a single metric against baseline."""
    metric_name: str
    baseline_value: float
    current_value: float
    delta: float
    regressed: bool  # True if current < baseline - tolerance


@dataclass
class RegressionReport:
    """Complete regression comparison report."""
    results: list[RegressionResult] = field(default_factory=list)
    any_regression: bool = False
    baseline_date: str = ""

    def to_dict(self) -> dict:
        return {
            "any_regression": self.any_regression,
            "baseline_date": self.baseline_date,
            "results": [
                {
                    "metric_name": r.metric_name,
                    "baseline_value": round(r.baseline_value, 4),
                    "current_value": round(r.current_value, 4),
                    "delta": round(r.delta, 4),
                    "regressed": r.regressed,
                }
                for r in self.results
            ],
        }


def load_baseline() -> dict | None:
    """Load baseline.json if it exists.

    Returns:
        Baseline dict or None if file doesn't exist or is empty.
    """
    if not BASELINE_FILE.exists():
        return None
    try:
        with open(BASELINE_FILE) as f:
            data = json.load(f)
        if not data:
            return None
        return data
    except (json.JSONDecodeError, OSError):
        return None


def save_baseline(
    extraction_report=None,
    classification_report=None,
    rag_report=None,
    validation_report=None,
) -> dict:
    """Save current eval scores as the new baseline.

    Args:
        extraction_report: EvalReport from ExtractionEvaluator
        classification_report: ClassificationEvalReport from ClassificationEvaluator
        rag_report: RAGEvalReport from RAGEvaluator
        validation_report: ValidationEvalReport from ValidationEvaluator

    Returns:
        The saved baseline dict.
    """
    baseline: dict = {
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }

    if extraction_report is not None:
        per_type = {}
        for dr in extraction_report.document_results:
            if dr.pass2_score is not None:
                per_type[dr.document_type] = dr.pass2_score.overall_accuracy
        baseline["extraction"] = {
            "pass1_accuracy": extraction_report.overall_pass1_accuracy,
            "pass2_accuracy": extraction_report.overall_pass2_accuracy,
            "per_type": per_type,
        }

    if classification_report is not None:
        baseline["classification"] = {
            "accuracy": classification_report.accuracy,
            "per_type": classification_report.per_type_accuracy,
        }

    if rag_report is not None:
        baseline["rag"] = {
            "hit_rate": rag_report.hit_rate,
            "mrr": rag_report.mrr,
            "answer_accuracy": rag_report.answer_accuracy,
        }

    if validation_report is not None:
        baseline["validation"] = {
            "precision": validation_report.overall_precision,
            "recall": validation_report.overall_recall,
            "f1": validation_report.overall_f1,
        }

    with open(BASELINE_FILE, "w") as f:
        json.dump(baseline, f, indent=2, default=str)

    logger.info("Baseline saved to %s", BASELINE_FILE)
    return baseline


def compare_to_baseline(
    extraction_report=None,
    classification_report=None,
    rag_report=None,
    validation_report=None,
    tolerance: float = 0.02,
) -> RegressionReport:
    """Compare current eval results against saved baseline.

    Args:
        tolerance: How much a metric can drop before being flagged as a regression.
            Default 0.02 = 2% absolute drop allowed.

    Returns:
        RegressionReport with per-metric comparisons and regression flag.
    """
    baseline = load_baseline()
    report = RegressionReport()

    if baseline is None:
        logger.warning("No baseline found — cannot compare")
        return report

    report.baseline_date = baseline.get("saved_at", "")

    def _check(metric_name: str, baseline_val: float, current_val: float):
        delta = current_val - baseline_val
        regressed = current_val < baseline_val - tolerance
        report.results.append(RegressionResult(
            metric_name=metric_name,
            baseline_value=baseline_val,
            current_value=current_val,
            delta=delta,
            regressed=regressed,
        ))
        if regressed:
            report.any_regression = True

    # Extraction metrics
    if extraction_report is not None and "extraction" in baseline:
        bl = baseline["extraction"]
        _check("extraction.pass1_accuracy", bl.get("pass1_accuracy", 0), extraction_report.overall_pass1_accuracy)
        _check("extraction.pass2_accuracy", bl.get("pass2_accuracy", 0), extraction_report.overall_pass2_accuracy)

    # Classification metrics
    if classification_report is not None and "classification" in baseline:
        bl = baseline["classification"]
        _check("classification.accuracy", bl.get("accuracy", 0), classification_report.accuracy)

    # RAG metrics
    if rag_report is not None and "rag" in baseline:
        bl = baseline["rag"]
        _check("rag.hit_rate", bl.get("hit_rate", 0), rag_report.hit_rate)
        _check("rag.mrr", bl.get("mrr", 0), rag_report.mrr)
        _check("rag.answer_accuracy", bl.get("answer_accuracy", 0), rag_report.answer_accuracy)

    # Validation metrics
    if validation_report is not None and "validation" in baseline:
        bl = baseline["validation"]
        _check("validation.precision", bl.get("precision", 0), validation_report.overall_precision)
        _check("validation.recall", bl.get("recall", 0), validation_report.overall_recall)
        _check("validation.f1", bl.get("f1", 0), validation_report.overall_f1)

    logger.info(
        "Baseline comparison: %d metrics, %s regressions detected",
        len(report.results),
        "YES" if report.any_regression else "no",
    )

    return report
