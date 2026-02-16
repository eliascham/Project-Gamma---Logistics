"""Tests for reconciliation matchers and engine."""

import pytest

from app.reconciliation_engine.matchers import (
    compute_composite_confidence,
    match_by_amount,
    match_by_date,
    match_by_reference,
)


# ── Pure matcher function tests ──


class TestMatchByReference:
    """Tests for match_by_reference."""

    def test_exact_match(self):
        is_match, conf = match_by_reference("SHP-2025-00001", "SHP-2025-00001")
        assert is_match is True
        assert conf == 1.0

    def test_case_insensitive(self):
        is_match, _ = match_by_reference("shp-2025-00001", "SHP-2025-00001")
        assert is_match is True

    def test_with_whitespace(self):
        is_match, _ = match_by_reference("  SHP-001 ", "SHP-001")
        assert is_match is True

    def test_no_match(self):
        is_match, conf = match_by_reference("SHP-001", "SHP-002")
        assert is_match is False
        assert conf == 0.0

    def test_none_values(self):
        is_match, _ = match_by_reference(None, "SHP-001")
        assert is_match is False

        is_match, _ = match_by_reference("SHP-001", None)
        assert is_match is False


class TestMatchByAmount:
    """Tests for match_by_amount."""

    def test_exact_match(self):
        is_match, conf = match_by_amount(1000.0, 1000.0)
        assert is_match is True
        assert conf == 1.0

    def test_within_tolerance(self):
        is_match, conf = match_by_amount(1000.0, 1010.0, tolerance_pct=0.02)
        assert is_match is True
        assert conf > 0.8

    def test_outside_tolerance(self):
        is_match, conf = match_by_amount(1000.0, 1050.0, tolerance_pct=0.02)
        assert is_match is False
        assert conf == 0.0

    def test_none_values(self):
        is_match, _ = match_by_amount(None, 1000.0)
        assert is_match is False

    def test_zero_amounts(self):
        is_match, conf = match_by_amount(0.0, 0.0)
        assert is_match is True
        assert conf == 1.0


class TestMatchByDate:
    """Tests for match_by_date."""

    def test_same_date(self):
        is_match, conf = match_by_date("2025-10-15T00:00:00+00:00", "2025-10-15T00:00:00+00:00")
        assert is_match is True
        assert conf == 1.0

    def test_within_tolerance(self):
        is_match, conf = match_by_date(
            "2025-10-15T00:00:00+00:00", "2025-10-17T00:00:00+00:00", tolerance_days=3
        )
        assert is_match is True
        assert conf > 0.5

    def test_outside_tolerance(self):
        is_match, _ = match_by_date(
            "2025-10-15T00:00:00+00:00", "2025-10-25T00:00:00+00:00", tolerance_days=3
        )
        assert is_match is False

    def test_none_values(self):
        is_match, _ = match_by_date(None, "2025-10-15T00:00:00+00:00")
        assert is_match is False

    def test_invalid_date(self):
        is_match, _ = match_by_date("not-a-date", "2025-10-15T00:00:00+00:00")
        assert is_match is False


class TestCompositeConfidence:
    """Tests for compute_composite_confidence."""

    def test_all_perfect(self):
        conf = compute_composite_confidence(1.0, 1.0, 1.0)
        assert conf == 1.0

    def test_all_zero(self):
        conf = compute_composite_confidence(0.0, 0.0, 0.0)
        assert conf == 0.0

    def test_weighted(self):
        # ref=1.0*0.5 + amt=0.0*0.3 + date=0.0*0.2 = 0.5
        conf = compute_composite_confidence(1.0, 0.0, 0.0)
        assert conf == 0.5

    def test_mixed(self):
        # ref=0.8*0.5 + amt=0.6*0.3 + date=0.4*0.2 = 0.4+0.18+0.08 = 0.66
        conf = compute_composite_confidence(0.8, 0.6, 0.4)
        assert conf == 0.66
