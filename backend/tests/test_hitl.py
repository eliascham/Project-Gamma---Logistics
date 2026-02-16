"""Tests for HITLService, ReviewTriggers, and review queue state machine."""

import uuid

import pytest
from unittest.mock import MagicMock

from app.hitl_workflow.service import HITLService
from app.hitl_workflow.triggers import (
    should_review_allocation,
    should_review_anomaly,
    should_review_reconciliation,
)
from app.models.review import ReviewItem, ReviewItemType, ReviewStatus


# ── Pure function tests (no DB needed) ──


class TestReviewTriggers:
    """Tests for ReviewTriggers pure functions."""

    def test_allocation_low_confidence_triggers_review(self):
        needs_review, reason = should_review_allocation(
            total_amount=500, min_confidence=0.70
        )
        assert needs_review is True
        assert "Low confidence" in reason

    def test_allocation_high_value_triggers_review(self):
        needs_review, reason = should_review_allocation(
            total_amount=15000, min_confidence=0.95
        )
        assert needs_review is True
        assert "High-value" in reason

    def test_allocation_auto_approved(self):
        needs_review, reason = should_review_allocation(
            total_amount=500, min_confidence=0.90
        )
        assert needs_review is False
        assert "Auto-approved" in reason

    def test_allocation_none_values(self):
        needs_review, _ = should_review_allocation(
            total_amount=None, min_confidence=None
        )
        assert needs_review is False

    def test_anomaly_high_severity_triggers_review(self):
        needs_review, reason = should_review_anomaly("high", "duplicate_invoice")
        assert needs_review is True
        assert "High-severity" in reason

    def test_anomaly_critical_triggers_review(self):
        needs_review, _ = should_review_anomaly("critical", "budget_overrun")
        assert needs_review is True

    def test_anomaly_medium_triggers_review(self):
        needs_review, _ = should_review_anomaly("medium", "misallocated_cost")
        assert needs_review is True

    def test_anomaly_low_no_review(self):
        needs_review, reason = should_review_anomaly("low", "unusual_amount")
        assert needs_review is False
        assert "informational" in reason.lower()

    def test_reconciliation_mismatches_trigger_review(self):
        needs_review, reason = should_review_reconciliation(
            match_confidence=0.8, mismatch_count=5, total_records=100
        )
        assert needs_review is True
        assert "5 mismatched" in reason

    def test_reconciliation_all_matched_no_review(self):
        needs_review, _ = should_review_reconciliation(
            match_confidence=1.0, mismatch_count=0, total_records=100
        )
        assert needs_review is False


# ── HITLService tests (need DB) ──


class TestHITLService:
    """Tests for HITLService state machine."""

    @pytest.fixture
    def hitl_service(self):
        settings = MagicMock()
        settings.hitl_auto_approve_dollar_threshold = 1000.0
        settings.hitl_high_risk_dollar_threshold = 10000.0
        return HITLService(settings)

    @pytest.mark.asyncio
    async def test_create_review_item_pending(self, db_session, hitl_service):
        """Test creating a review item that stays pending."""
        item = await hitl_service.create_review_item(
            db_session,
            item_type=ReviewItemType.COST_ALLOCATION,
            entity_id=uuid.uuid4(),
            entity_type="cost_allocation",
            title="Test allocation review",
            dollar_amount=5000,
            confidence=0.70,
        )

        assert item.id is not None
        assert item.status == ReviewStatus.PENDING_REVIEW
        assert item.auto_approve_eligible is False

    @pytest.mark.asyncio
    async def test_create_review_item_auto_approved(self, db_session, hitl_service):
        """Test auto-approval for low-risk, high-confidence items."""
        item = await hitl_service.create_review_item(
            db_session,
            item_type=ReviewItemType.COST_ALLOCATION,
            entity_id=uuid.uuid4(),
            entity_type="cost_allocation",
            title="Small auto-approved allocation",
            dollar_amount=500,
            confidence=0.95,
        )

        assert item.status == ReviewStatus.AUTO_APPROVED
        assert item.auto_approve_eligible is True

    @pytest.mark.asyncio
    async def test_create_review_item_high_risk(self, db_session, hitl_service):
        """Test high-risk items always go to pending review."""
        item = await hitl_service.create_review_item(
            db_session,
            item_type=ReviewItemType.COST_ALLOCATION,
            entity_id=uuid.uuid4(),
            entity_type="cost_allocation",
            title="High-value allocation",
            dollar_amount=15000,
            confidence=0.99,
        )

        assert item.status == ReviewStatus.PENDING_REVIEW
        assert item.auto_approve_eligible is False

    @pytest.mark.asyncio
    async def test_review_item_approve(self, db_session, hitl_service):
        """Test approving a review item."""
        item = await hitl_service.create_review_item(
            db_session,
            item_type=ReviewItemType.ANOMALY,
            entity_id=uuid.uuid4(),
            entity_type="anomaly_flag",
            title="Test anomaly",
        )

        reviewed = await hitl_service.review_item(
            db_session, item.id, action="approve", reviewed_by="tester", notes="Looks good",
        )

        assert reviewed.status == ReviewStatus.APPROVED
        assert reviewed.reviewed_by == "tester"
        assert reviewed.review_notes == "Looks good"
        assert reviewed.reviewed_at is not None

    @pytest.mark.asyncio
    async def test_review_item_reject(self, db_session, hitl_service):
        """Test rejecting a review item."""
        item = await hitl_service.create_review_item(
            db_session,
            item_type=ReviewItemType.ANOMALY,
            entity_id=uuid.uuid4(),
            entity_type="anomaly_flag",
            title="Bad item",
        )

        reviewed = await hitl_service.review_item(
            db_session, item.id, action="reject",
        )
        assert reviewed.status == ReviewStatus.REJECTED

    @pytest.mark.asyncio
    async def test_review_item_escalate(self, db_session, hitl_service):
        """Test escalating a review item."""
        item = await hitl_service.create_review_item(
            db_session,
            item_type=ReviewItemType.RECONCILIATION_MISMATCH,
            entity_id=uuid.uuid4(),
            entity_type="reconciliation_run",
            title="Needs manager review",
        )

        reviewed = await hitl_service.review_item(
            db_session, item.id, action="escalate",
        )
        assert reviewed.status == ReviewStatus.ESCALATED

    @pytest.mark.asyncio
    async def test_review_item_invalid_action(self, db_session, hitl_service):
        """Test invalid action raises ValueError."""
        item = await hitl_service.create_review_item(
            db_session,
            item_type=ReviewItemType.ANOMALY,
            entity_id=uuid.uuid4(),
            entity_type="anomaly_flag",
            title="Test",
        )

        with pytest.raises(ValueError, match="Invalid action"):
            await hitl_service.review_item(db_session, item.id, action="invalid")

    @pytest.mark.asyncio
    async def test_review_item_not_found(self, db_session, hitl_service):
        """Test reviewing non-existent item raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            await hitl_service.review_item(
                db_session, uuid.uuid4(), action="approve",
            )

    @pytest.mark.asyncio
    async def test_get_queue(self, db_session, hitl_service):
        """Test getting the review queue."""
        for i in range(3):
            await hitl_service.create_review_item(
                db_session,
                item_type=ReviewItemType.ANOMALY,
                entity_id=uuid.uuid4(),
                entity_type="anomaly_flag",
                title=f"Item {i}",
            )

        items, total = await hitl_service.get_queue(db_session)
        assert total == 3
        assert len(items) == 3

    @pytest.mark.asyncio
    async def test_get_stats(self, db_session, hitl_service):
        """Test getting queue stats."""
        await hitl_service.create_review_item(
            db_session,
            item_type=ReviewItemType.ANOMALY,
            entity_id=uuid.uuid4(),
            entity_type="anomaly_flag",
            title="Pending item",
        )

        stats = await hitl_service.get_stats(db_session)
        assert stats["total"] >= 1
        assert "pending_review" in stats
