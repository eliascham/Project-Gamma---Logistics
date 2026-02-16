"""Tests for anomaly detection — pure detectors and AnomalyFlagger service."""

import uuid

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.anomaly_flagger.detectors import (
    detect_budget_overrun,
    detect_duplicate,
    detect_low_confidence_items,
    detect_unusual_amount,
)


# ── Pure detector function tests ──


class TestDetectDuplicate:
    """Tests for detect_duplicate pure function."""

    def test_duplicate_found(self):
        existing = [
            {"invoice_number": "INV-001", "vendor": "Maersk", "document_id": "abc"},
        ]
        result = detect_duplicate("INV-001", "Maersk", existing)
        assert result is not None
        assert result["invoice_number"] == "INV-001"
        assert result["vendor"] == "Maersk"

    def test_no_duplicate(self):
        existing = [
            {"invoice_number": "INV-002", "vendor": "MSC", "document_id": "abc"},
        ]
        result = detect_duplicate("INV-001", "Maersk", existing)
        assert result is None

    def test_case_insensitive_vendor(self):
        existing = [
            {"invoice_number": "INV-001", "vendor": "MAERSK", "document_id": "abc"},
        ]
        result = detect_duplicate("INV-001", "maersk", existing)
        assert result is not None

    def test_empty_existing(self):
        result = detect_duplicate("INV-001", "Maersk", [])
        assert result is None

    def test_different_vendor_same_invoice(self):
        existing = [
            {"invoice_number": "INV-001", "vendor": "MSC", "document_id": "abc"},
        ]
        result = detect_duplicate("INV-001", "Maersk", existing)
        assert result is None


class TestDetectBudgetOverrun:
    """Tests for detect_budget_overrun pure function."""

    def test_overrun_detected(self):
        result = detect_budget_overrun(
            "PROJ-001", 50000, budget_amount=100000, spent_amount=65000, threshold=0.1
        )
        assert result is not None
        assert result["overrun_pct"] > 10

    def test_within_budget(self):
        result = detect_budget_overrun(
            "PROJ-001", 5000, budget_amount=100000, spent_amount=50000, threshold=0.1
        )
        assert result is None

    def test_exactly_at_threshold(self):
        # 90000 + 20000 = 110000 / 100000 = 10% overrun = threshold
        result = detect_budget_overrun(
            "PROJ-001", 20000, budget_amount=100000, spent_amount=90000, threshold=0.1
        )
        assert result is None  # at threshold, not over

    def test_zero_budget(self):
        result = detect_budget_overrun(
            "PROJ-001", 1000, budget_amount=0, spent_amount=0, threshold=0.1
        )
        assert result is None


class TestDetectLowConfidenceItems:
    """Tests for detect_low_confidence_items pure function."""

    def test_items_below_threshold(self):
        items = [
            {"index": 0, "description": "Ocean freight", "amount": 5000, "confidence": 0.90},
            {"index": 1, "description": "Customs duty", "amount": 2000, "confidence": 0.60},
            {"index": 2, "description": "Drayage", "amount": 1000, "confidence": 0.80},
        ]
        flagged = detect_low_confidence_items(items, confidence_threshold=0.85)
        assert len(flagged) == 2  # indices 1 and 2
        assert flagged[0]["line_item_index"] == 1
        assert flagged[1]["line_item_index"] == 2

    def test_all_above_threshold(self):
        items = [
            {"index": 0, "description": "Ocean freight", "amount": 5000, "confidence": 0.95},
        ]
        flagged = detect_low_confidence_items(items, confidence_threshold=0.85)
        assert flagged == []

    def test_empty_items(self):
        flagged = detect_low_confidence_items([])
        assert flagged == []


class TestDetectUnusualAmount:
    """Tests for detect_unusual_amount pure function."""

    def test_outlier_detected(self):
        historical = [100, 110, 105, 95, 100, 108, 102, 98, 107, 103]
        result = detect_unusual_amount(500, historical, std_multiplier=3.0)
        assert result is not None
        assert result["z_score"] > 3.0

    def test_normal_amount(self):
        historical = [100, 110, 105, 95, 100, 108, 102, 98, 107, 103]
        result = detect_unusual_amount(105, historical, std_multiplier=3.0)
        assert result is None

    def test_insufficient_data(self):
        result = detect_unusual_amount(500, [100, 200], std_multiplier=3.0)
        assert result is None  # fewer than 5 data points

    def test_zero_std_dev(self):
        historical = [100, 100, 100, 100, 100]
        result = detect_unusual_amount(200, historical)
        assert result is None  # std_dev is 0
