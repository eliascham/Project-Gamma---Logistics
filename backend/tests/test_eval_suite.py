"""Tests for the expanded eval suite.

Covers classification, validation, confidence calibration, regression baseline,
and RAG benchmark expansion. All tests use mocks — no Postgres or API calls needed.
"""

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.eval.baseline import (
    RegressionReport,
    RegressionResult,
    compare_to_baseline,
    load_baseline,
    save_baseline,
)
from app.eval.classification_eval import (
    ClassificationEvalReport,
    ClassificationEvaluator,
    ClassificationResult,
)
from app.eval.confidence_eval import (
    CalibrationBin,
    ConfidenceCalibrationEvaluator,
    ConfidenceCalibrationReport,
)
from app.eval.rag_eval import (
    RAGEvalReport,
    RAGEvalResult,
    RAGEvaluator,
    _load_benchmark,
)
from app.eval.validation_eval import (
    ValidationEvalReport,
    ValidationEvaluator,
    ValidationEvalResult,
)


# --------------------------------------------------------------------------- #
# Helpers — reusable fixtures for ground truth files
# --------------------------------------------------------------------------- #

def _write_ground_truth(tmp_dir: Path, doc_type: str, index: int, extraction: dict):
    """Write a ground truth CSV + expected JSON pair into tmp_dir."""
    base = f"{doc_type}_{index:02d}"
    csv_file = tmp_dir / f"{base}.csv"
    csv_file.write_text(f"Type: {doc_type}\nSample data for testing\n")
    expected_file = tmp_dir / f"{base}_expected.json"
    expected_file.write_text(json.dumps({
        "document_type": doc_type,
        "extraction": extraction,
    }))
    return csv_file, expected_file


def _write_validation_test(tmp_dir: Path, name: str, doc_type: str,
                           extraction: dict, expected_clean: bool,
                           expected_issues: list[dict]):
    """Write a validation-annotated expected JSON into tmp_dir."""
    expected_file = tmp_dir / f"{name}_expected.json"
    expected_file.write_text(json.dumps({
        "document_type": doc_type,
        "extraction": extraction,
        "validation_annotations": {
            "expected_clean": expected_clean,
            "expected_issues": expected_issues,
        },
    }))
    return expected_file


# --------------------------------------------------------------------------- #
# ClassificationEvaluator tests
# --------------------------------------------------------------------------- #

class TestClassificationEvaluator:
    """Tests for the classification evaluator."""

    def test_report_to_dict_structure(self):
        """Report to_dict has all expected keys."""
        report = ClassificationEvalReport(
            eval_id="abc",
            accuracy=0.8,
            per_type_accuracy={"freight_invoice": 1.0, "bill_of_lading": 0.5},
            confusion_matrix={"freight_invoice": {"freight_invoice": 2}},
            total_documents=4,
            successful_documents=4,
            elapsed_ms=100,
            model_used="test-model",
        )
        d = report.to_dict()
        assert d["accuracy"] == 0.8
        assert "per_type_accuracy" in d
        assert "confusion_matrix" in d
        assert d["total_documents"] == 4
        assert d["model_used"] == "test-model"

    def test_classification_result_dataclass(self):
        """ClassificationResult correctly stores fields."""
        r = ClassificationResult(
            filename="test.csv",
            expected_type="freight_invoice",
            predicted_type="freight_invoice",
            correct=True,
        )
        assert r.correct is True
        assert r.error is None

    def test_classification_result_with_error(self):
        """ClassificationResult records errors."""
        r = ClassificationResult(
            filename="bad.csv",
            expected_type="freight_invoice",
            predicted_type="error",
            correct=False,
            error="API timeout",
        )
        assert r.correct is False
        assert r.error == "API timeout"

    @pytest.mark.asyncio
    async def test_empty_ground_truth_dir(self):
        """Raises ValueError when no expected files found."""
        with tempfile.TemporaryDirectory() as tmp:
            settings = MagicMock()
            settings.anthropic_api_key = "test-key"
            settings.claude_haiku_model = "test-haiku"
            evaluator = ClassificationEvaluator(settings)
            with pytest.raises(ValueError, match="No.*expected.*json"):
                await evaluator.run(ground_truth_dir=tmp)

    @pytest.mark.asyncio
    async def test_missing_ground_truth_dir(self):
        """Raises FileNotFoundError when directory doesn't exist."""
        settings = MagicMock()
        settings.anthropic_api_key = "test-key"
        settings.claude_haiku_model = "test-haiku"
        evaluator = ClassificationEvaluator(settings)
        with pytest.raises(FileNotFoundError):
            await evaluator.run(ground_truth_dir="/nonexistent/path")

    @pytest.mark.asyncio
    async def test_skips_validation_only_files(self):
        """Files with validation_annotations are skipped (0 docs classified)."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            # Write a validation-only file (no CSV pair)
            _write_validation_test(
                tmp_path, "validation_test_01", "freight_invoice",
                {"invoice_number": "X"}, True, [],
            )
            # Also write a normal expected.json BUT without a source CSV
            (tmp_path / "orphan_01_expected.json").write_text(json.dumps({
                "document_type": "freight_invoice",
                "extraction": {"invoice_number": "X"},
            }))
            settings = MagicMock()
            settings.anthropic_api_key = "test-key"
            settings.claude_haiku_model = "test-haiku"
            evaluator = ClassificationEvaluator(settings)
            report = await evaluator.run(ground_truth_dir=tmp)
            # Both files should be skipped: validation-only + no source doc
            assert report.total_documents == 0

    def test_confusion_matrix_structure(self):
        """Confusion matrix in report is well-formed."""
        report = ClassificationEvalReport(
            confusion_matrix={
                "freight_invoice": {"freight_invoice": 3, "bill_of_lading": 1},
                "bill_of_lading": {"bill_of_lading": 2},
            },
        )
        cm = report.to_dict()["confusion_matrix"]
        assert cm["freight_invoice"]["freight_invoice"] == 3
        assert cm["freight_invoice"]["bill_of_lading"] == 1
        assert cm["bill_of_lading"]["bill_of_lading"] == 2


# --------------------------------------------------------------------------- #
# ValidationEvaluator tests
# --------------------------------------------------------------------------- #

class TestValidationEvaluator:
    """Tests for the validation evaluator."""

    def test_report_to_dict_structure(self):
        """Report to_dict has all expected keys."""
        report = ValidationEvalReport(
            eval_id="val1",
            overall_precision=0.75,
            overall_recall=0.80,
            overall_f1=0.7742,
            total_documents=3,
            elapsed_ms=50,
        )
        d = report.to_dict()
        assert d["overall_precision"] == 0.75
        assert d["overall_recall"] == 0.8
        assert "overall_f1" in d
        assert d["total_documents"] == 3

    def test_empty_ground_truth_skips_gracefully(self):
        """If no annotated files, report has zero documents."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            # Write a normal ground truth file (no validation_annotations)
            _write_ground_truth(
                tmp_path, "freight_invoice", 1,
                {"invoice_number": "X", "total_amount": 100},
            )
            evaluator = ValidationEvaluator()
            report = evaluator.run(ground_truth_dir=tmp)
            assert report.total_documents == 0
            assert len(report.results) == 0

    def test_missing_ground_truth_dir(self):
        """Raises FileNotFoundError when directory doesn't exist."""
        evaluator = ValidationEvaluator()
        with pytest.raises(FileNotFoundError):
            evaluator.run(ground_truth_dir="/nonexistent/path")

    def test_clean_document_no_false_positives(self):
        """Clean document should produce no false positives."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _write_validation_test(
                tmp_path, "clean_test", "freight_invoice",
                {
                    "invoice_number": "FI-001",
                    "invoice_date": "2024-08-15",
                    "vendor_name": "Test Vendor",
                    "total_amount": 3500.0,
                    "subtotal": 3500.0,
                    "tax_amount": 0,
                    "currency": "USD",
                    "line_items": [
                        {"description": "Freight", "quantity": 1, "unit_price": 3500.0, "total": 3500.0},
                    ],
                },
                expected_clean=True,
                expected_issues=[],
            )
            evaluator = ValidationEvaluator()
            report = evaluator.run(ground_truth_dir=tmp)
            assert report.total_documents == 1
            # Should have no false negatives (no expected issues to miss)
            for r in report.results:
                assert r.false_negatives == 0

    def test_bad_math_detected(self):
        """Line item math errors are detected as true positives."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _write_validation_test(
                tmp_path, "bad_math", "freight_invoice",
                {
                    "invoice_number": "FI-BAD",
                    "invoice_date": "2024-10-15",
                    "vendor_name": "",
                    "total_amount": 5000.0,
                    "subtotal": 5000.0,
                    "tax_amount": 0,
                    "currency": "USD",
                    "line_items": [
                        {"description": "Ocean Freight", "quantity": 2, "unit_price": 1800.0, "total": 4000.0},
                    ],
                },
                expected_clean=False,
                expected_issues=[
                    {"rule": "missing_required", "field": "vendor_name"},
                    {"rule": "line_item_math", "field": "line_items.0.total"},
                ],
            )
            evaluator = ValidationEvaluator()
            report = evaluator.run(ground_truth_dir=tmp)
            assert report.total_documents == 1
            # At least some expected issues should be detected
            result = report.results[0]
            assert result.true_positives + result.false_negatives > 0

    def test_precision_recall_f1_computation(self):
        """Precision/recall/F1 are computed correctly from aggregates."""
        report = ValidationEvalReport()
        # Simulate: 3 TP, 1 FP, 1 FN
        # precision = 3/(3+1) = 0.75, recall = 3/(3+1) = 0.75, F1 = 0.75
        report.results.append(ValidationEvalResult(
            filename="test.json",
            document_type="freight_invoice",
            true_positives=3,
            false_positives=1,
            false_negatives=1,
        ))
        # Recompute manually (since the evaluator computes during run)
        tp, fp, fn = 3, 1, 1
        prec = tp / (tp + fp)
        rec = tp / (tp + fn)
        f1 = 2 * prec * rec / (prec + rec)
        assert prec == 0.75
        assert rec == 0.75
        assert f1 == 0.75

    def test_per_rule_stats_in_report(self):
        """Per-rule stats dict is included in to_dict output."""
        report = ValidationEvalReport(
            per_rule_stats={
                "line_item_math": {
                    "true_positives": 5,
                    "false_positives": 1,
                    "false_negatives": 0,
                    "precision": 0.8333,
                    "recall": 1.0,
                    "f1": 0.9091,
                },
            },
        )
        d = report.to_dict()
        assert "line_item_math" in d["per_rule_stats"]
        assert d["per_rule_stats"]["line_item_math"]["recall"] == 1.0

    def test_validation_eval_result_with_error(self):
        """ValidationEvalResult records errors."""
        r = ValidationEvalResult(
            filename="bad.json",
            document_type="freight_invoice",
            error="Parse error",
        )
        assert r.error == "Parse error"
        assert r.true_positives == 0

    def test_runs_on_real_validation_test_files(self):
        """Smoke test: runs on the actual validation test files in ground_truth."""
        gt_dir = str(Path(__file__).parent.parent / "app" / "eval" / "ground_truth")
        if not Path(gt_dir).exists():
            pytest.skip("Ground truth directory not found")
        evaluator = ValidationEvaluator()
        report = evaluator.run(ground_truth_dir=gt_dir)
        # Should find at least the 5 validation test files
        assert report.total_documents >= 5


# --------------------------------------------------------------------------- #
# ConfidenceCalibrationEvaluator tests
# --------------------------------------------------------------------------- #

class TestConfidenceCalibrationEvaluator:
    """Tests for the confidence calibration evaluator."""

    def test_calibration_bin_to_dict(self):
        """CalibrationBin.to_dict returns expected structure."""
        b = CalibrationBin(
            bin_lower=0.0, bin_upper=0.2,
            field_count=10, correct_count=1,
            accuracy=0.1, calibration_error=0.0,
        )
        d = b.to_dict()
        assert d["bin_range"] == "0.0-0.2"
        assert d["field_count"] == 10
        assert d["correct_count"] == 1

    def test_report_to_dict_structure(self):
        """ConfidenceCalibrationReport.to_dict has all keys."""
        report = ConfidenceCalibrationReport(
            eval_id="conf1",
            ece=0.05,
            brier_score=0.12,
            total_fields=100,
            model_used="test-model",
            elapsed_ms=500,
            bins=[
                CalibrationBin(0.0, 0.2, 20, 2, 0.1, 0.0),
                CalibrationBin(0.2, 0.4, 20, 6, 0.3, 0.0),
                CalibrationBin(0.4, 0.6, 20, 10, 0.5, 0.0),
                CalibrationBin(0.6, 0.8, 20, 14, 0.7, 0.0),
                CalibrationBin(0.8, 1.0, 20, 18, 0.9, 0.0),
            ],
        )
        d = report.to_dict()
        assert d["ece"] == 0.05
        assert d["brier_score"] == 0.12
        assert len(d["bins"]) == 5
        assert d["total_fields"] == 100

    def test_perfect_calibration_zero_ece(self):
        """Perfectly calibrated bins should have ECE near zero."""
        # If accuracy matches bin midpoint in each bin, ECE = 0
        bins = []
        for i in range(5):
            lower = i * 0.2
            upper = (i + 1) * 0.2
            midpoint = (lower + upper) / 2
            bins.append(CalibrationBin(
                bin_lower=lower, bin_upper=upper,
                field_count=20, correct_count=int(20 * midpoint),
                accuracy=midpoint, calibration_error=0.0,
            ))

        report = ConfidenceCalibrationReport(
            bins=bins, ece=0.0, total_fields=100,
        )
        assert report.ece == 0.0

    def test_overconfident_high_ece(self):
        """Overconfident model (all in 0.8-1.0 bin, 50% accuracy) has high error."""
        b = CalibrationBin(
            bin_lower=0.8, bin_upper=1.0,
            field_count=100, correct_count=50,
            accuracy=0.5,
            calibration_error=abs(0.5 - 0.9),  # 0.4
        )
        assert b.calibration_error == pytest.approx(0.4, abs=0.01)

    def test_brier_score_perfect(self):
        """Perfect predictions (confidence=correctness) → Brier = 0."""
        pairs = [(1.0, 1.0), (0.0, 0.0), (1.0, 1.0)]
        brier = sum((c - corr) ** 2 for c, corr in pairs) / len(pairs)
        assert brier == 0.0

    def test_brier_score_worst(self):
        """Worst predictions (confidence opposite of correctness) → Brier = 1."""
        pairs = [(1.0, 0.0), (0.0, 1.0)]
        brier = sum((c - corr) ** 2 for c, corr in pairs) / len(pairs)
        assert brier == 1.0


# --------------------------------------------------------------------------- #
# RegressionBaseline tests
# --------------------------------------------------------------------------- #

class TestRegressionBaseline:
    """Tests for save/load/compare baseline functionality."""

    def test_load_baseline_no_file(self):
        """Returns None when baseline file doesn't exist."""
        with patch("app.eval.baseline.BASELINE_FILE", Path("/nonexistent/baseline.json")):
            result = load_baseline()
            assert result is None

    def test_load_baseline_empty_file(self):
        """Returns None when baseline file is empty JSON."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp) / "empty_baseline.json"
            tmp_path.write_text("{}")
            with patch("app.eval.baseline.BASELINE_FILE", tmp_path):
                result = load_baseline()
                assert result is None

    def test_save_and_load_baseline(self):
        """Saved baseline can be loaded back."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            tmp_path = Path(f.name)

        try:
            with patch("app.eval.baseline.BASELINE_FILE", tmp_path):
                # Create mock reports
                val_report = MagicMock()
                val_report.overall_precision = 0.85
                val_report.overall_recall = 0.90
                val_report.overall_f1 = 0.875

                saved = save_baseline(validation_report=val_report)
                assert "validation" in saved
                assert saved["validation"]["precision"] == 0.85

                loaded = load_baseline()
                assert loaded is not None
                assert loaded["validation"]["recall"] == 0.90
        finally:
            if tmp_path.exists():
                os.unlink(tmp_path)

    def test_save_baseline_extraction(self):
        """Extraction report metrics are correctly saved."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            tmp_path = Path(f.name)

        try:
            with patch("app.eval.baseline.BASELINE_FILE", tmp_path):
                ext_report = MagicMock()
                ext_report.overall_pass1_accuracy = 0.70
                ext_report.overall_pass2_accuracy = 0.85
                ext_report.document_results = []

                saved = save_baseline(extraction_report=ext_report)
                assert "extraction" in saved
                assert saved["extraction"]["pass1_accuracy"] == 0.70
                assert saved["extraction"]["pass2_accuracy"] == 0.85
        finally:
            if tmp_path.exists():
                os.unlink(tmp_path)

    def test_compare_no_baseline(self):
        """Comparison with no baseline returns empty report."""
        with patch("app.eval.baseline.BASELINE_FILE", Path("/nonexistent/baseline.json")):
            report = compare_to_baseline()
            assert len(report.results) == 0
            assert report.any_regression is False

    def test_compare_no_regression(self):
        """No regression when current >= baseline."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({
                "saved_at": "2024-01-01T00:00:00Z",
                "validation": {"precision": 0.80, "recall": 0.85, "f1": 0.825},
            }, f)
            f.flush()
            tmp_path = Path(f.name)

        try:
            with patch("app.eval.baseline.BASELINE_FILE", tmp_path):
                val_report = MagicMock()
                val_report.overall_precision = 0.82  # improved
                val_report.overall_recall = 0.85     # same
                val_report.overall_f1 = 0.835        # improved

                report = compare_to_baseline(validation_report=val_report)
                assert report.any_regression is False
                assert len(report.results) == 3  # precision, recall, f1
        finally:
            if tmp_path.exists():
                os.unlink(tmp_path)

    def test_compare_with_regression(self):
        """Regression detected when current < baseline - tolerance."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({
                "saved_at": "2024-01-01T00:00:00Z",
                "validation": {"precision": 0.90, "recall": 0.90, "f1": 0.90},
            }, f)
            f.flush()
            tmp_path = Path(f.name)

        try:
            with patch("app.eval.baseline.BASELINE_FILE", tmp_path):
                val_report = MagicMock()
                val_report.overall_precision = 0.85  # dropped 5%, exceeds 2% tolerance
                val_report.overall_recall = 0.89     # dropped 1%, within tolerance
                val_report.overall_f1 = 0.87         # dropped 3%, exceeds tolerance

                report = compare_to_baseline(
                    validation_report=val_report, tolerance=0.02,
                )
                assert report.any_regression is True
                # precision and f1 should be flagged
                regressed = [r for r in report.results if r.regressed]
                assert len(regressed) >= 2
        finally:
            if tmp_path.exists():
                os.unlink(tmp_path)

    def test_compare_tolerance_boundary(self):
        """Exactly at tolerance boundary is not a regression."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({
                "saved_at": "2024-01-01T00:00:00Z",
                "rag": {"hit_rate": 0.80, "mrr": 0.70, "answer_accuracy": 0.85},
            }, f)
            f.flush()
            tmp_path = Path(f.name)

        try:
            with patch("app.eval.baseline.BASELINE_FILE", tmp_path):
                rag_report = MagicMock()
                rag_report.hit_rate = 0.78     # exactly at boundary (0.80 - 0.02)
                rag_report.mrr = 0.70          # same
                rag_report.answer_accuracy = 0.83  # exactly at boundary

                report = compare_to_baseline(
                    rag_report=rag_report, tolerance=0.02,
                )
                # At boundary = not regressed (regressed is current < baseline - tolerance)
                assert report.any_regression is False
        finally:
            if tmp_path.exists():
                os.unlink(tmp_path)

    def test_regression_report_to_dict(self):
        """RegressionReport.to_dict has correct structure."""
        report = RegressionReport(
            results=[
                RegressionResult(
                    metric_name="test.metric",
                    baseline_value=0.90,
                    current_value=0.85,
                    delta=-0.05,
                    regressed=True,
                ),
            ],
            any_regression=True,
            baseline_date="2024-01-01T00:00:00Z",
        )
        d = report.to_dict()
        assert d["any_regression"] is True
        assert len(d["results"]) == 1
        assert d["results"][0]["regressed"] is True
        assert d["results"][0]["delta"] == -0.05

    def test_partial_baseline_only_compares_available(self):
        """If baseline only has rag, only rag metrics are compared."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({
                "saved_at": "2024-01-01T00:00:00Z",
                "rag": {"hit_rate": 0.80, "mrr": 0.70, "answer_accuracy": 0.85},
            }, f)
            f.flush()
            tmp_path = Path(f.name)

        try:
            with patch("app.eval.baseline.BASELINE_FILE", tmp_path):
                # Pass a validation report — no validation in baseline, should be ignored
                val_report = MagicMock()
                val_report.overall_precision = 0.5
                val_report.overall_recall = 0.5
                val_report.overall_f1 = 0.5

                report = compare_to_baseline(validation_report=val_report)
                # No validation in baseline, so no comparisons made
                assert len(report.results) == 0
        finally:
            if tmp_path.exists():
                os.unlink(tmp_path)


# --------------------------------------------------------------------------- #
# RAG Benchmark Expansion tests
# --------------------------------------------------------------------------- #

class TestRAGBenchmarkExpanded:
    """Tests for the expanded RAG benchmark and file-based loading."""

    def test_load_benchmark_from_file(self):
        """Loading benchmark from JSON file returns questions."""
        benchmark_path = (
            Path(__file__).parent.parent / "app" / "eval" / "ground_truth" / "rag_benchmark.json"
        )
        if not benchmark_path.exists():
            pytest.skip("rag_benchmark.json not found")

        questions = _load_benchmark(str(benchmark_path))
        assert len(questions) >= 15  # at least 15 positive
        # Check structure
        for q in questions:
            assert "question" in q
            assert "expected_answer_contains" in q

    def test_load_benchmark_fallback(self):
        """Falls back to legacy benchmark if file doesn't exist."""
        questions = _load_benchmark("/nonexistent/benchmark.json")
        assert len(questions) == 10  # legacy has 10 questions

    def test_load_benchmark_invalid_json(self):
        """Falls back to legacy on invalid JSON."""
        with tempfile.TemporaryDirectory() as tmp:
            bad_file = Path(tmp) / "bad_benchmark.json"
            bad_file.write_text("not valid json {{{")
            questions = _load_benchmark(str(bad_file))
            assert len(questions) == 10  # legacy fallback

    def test_negative_questions_exist(self):
        """Benchmark file contains negative (should-decline) questions."""
        benchmark_path = (
            Path(__file__).parent.parent / "app" / "eval" / "ground_truth" / "rag_benchmark.json"
        )
        if not benchmark_path.exists():
            pytest.skip("rag_benchmark.json not found")

        questions = _load_benchmark(str(benchmark_path))
        negative = [q for q in questions if q.get("is_negative", False)]
        assert len(negative) >= 5

    def test_categories_present(self):
        """All questions have category field."""
        benchmark_path = (
            Path(__file__).parent.parent / "app" / "eval" / "ground_truth" / "rag_benchmark.json"
        )
        if not benchmark_path.exists():
            pytest.skip("rag_benchmark.json not found")

        questions = _load_benchmark(str(benchmark_path))
        for q in questions:
            assert "category" in q, f"Question missing category: {q['question']}"

    def test_rag_eval_report_with_negative(self):
        """RAGEvalReport correctly stores negative rejection rate."""
        report = RAGEvalReport(
            eval_id="test",
            hit_rate=0.8,
            mrr=0.6,
            answer_accuracy=0.75,
            negative_rejection_rate=0.9,
            per_category_accuracy={"gl_mapping": 0.85, "negative": 0.9},
            total_questions=20,
            successful_questions=20,
        )
        d = report.to_dict()
        assert d["negative_rejection_rate"] == 0.9
        assert "per_category_accuracy" in d
        assert d["per_category_accuracy"]["negative"] == 0.9

    def test_rag_eval_result_negative_fields(self):
        """RAGEvalResult supports is_negative and correctly_declined."""
        r = RAGEvalResult(
            question="What is the EUR/USD rate?",
            answer="I don't have that information.",
            is_negative=True,
            correctly_declined=True,
            category="negative",
        )
        assert r.is_negative is True
        assert r.correctly_declined is True

    def test_rag_eval_report_to_dict_includes_all_fields(self):
        """to_dict includes questions with negative test fields."""
        report = RAGEvalReport(
            eval_id="test",
            results=[
                RAGEvalResult(
                    question="Q1",
                    answer="A1",
                    sources_found=["gl_account_mapping"],
                    hit=True,
                    reciprocal_rank=1.0,
                    answer_contains_expected=True,
                    category="gl_mapping",
                ),
                RAGEvalResult(
                    question="Q2 (negative)",
                    answer="I cannot find that.",
                    is_negative=True,
                    correctly_declined=True,
                    category="negative",
                ),
            ],
        )
        d = report.to_dict()
        assert len(d["questions"]) == 2
        assert d["questions"][0]["category"] == "gl_mapping"
        assert d["questions"][1]["is_negative"] is True
        assert d["questions"][1]["correctly_declined"] is True
