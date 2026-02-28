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


# ── Inline field editing tests ──


class TestUpdateFields:
    """Tests for inline field editing via HITLService.update_fields()."""

    @pytest.fixture
    def hitl_service(self):
        settings = MagicMock()
        settings.hitl_auto_approve_dollar_threshold = 1000.0
        settings.hitl_high_risk_dollar_threshold = 10000.0
        return HITLService(settings)

    @pytest.mark.asyncio
    async def test_update_title(self, db_session, hitl_service):
        """Test updating the title field."""
        item = await hitl_service.create_review_item(
            db_session,
            item_type=ReviewItemType.ANOMALY,
            entity_id=uuid.uuid4(),
            entity_type="anomaly_flag",
            title="Original Title",
        )

        updated = await hitl_service.update_fields(
            db_session, item.id, title="New Title", updated_by="editor",
        )
        assert updated.title == "New Title"

    @pytest.mark.asyncio
    async def test_update_assigned_to(self, db_session, hitl_service):
        """Test assigning a review item to someone."""
        item = await hitl_service.create_review_item(
            db_session,
            item_type=ReviewItemType.ANOMALY,
            entity_id=uuid.uuid4(),
            entity_type="anomaly_flag",
            title="Unassigned item",
        )
        assert item.assigned_to is None

        updated = await hitl_service.update_fields(
            db_session, item.id, assigned_to="jane.doe@company.com",
        )
        assert updated.assigned_to == "jane.doe@company.com"

    @pytest.mark.asyncio
    async def test_update_severity(self, db_session, hitl_service):
        """Test changing severity."""
        item = await hitl_service.create_review_item(
            db_session,
            item_type=ReviewItemType.ANOMALY,
            entity_id=uuid.uuid4(),
            entity_type="anomaly_flag",
            title="Low severity item",
            severity="low",
        )

        updated = await hitl_service.update_fields(
            db_session, item.id, severity="critical",
        )
        assert updated.severity == "critical"

    @pytest.mark.asyncio
    async def test_update_multiple_fields(self, db_session, hitl_service):
        """Test updating multiple fields at once."""
        item = await hitl_service.create_review_item(
            db_session,
            item_type=ReviewItemType.COST_ALLOCATION,
            entity_id=uuid.uuid4(),
            entity_type="cost_allocation",
            title="Multi-edit test",
            dollar_amount=5000,
        )

        updated = await hitl_service.update_fields(
            db_session, item.id,
            title="Updated Multi-edit",
            description="Added description",
            dollar_amount=6000,
        )
        assert updated.title == "Updated Multi-edit"
        assert updated.description == "Added description"
        assert updated.dollar_amount == 6000

    @pytest.mark.asyncio
    async def test_update_noop_no_changes(self, db_session, hitl_service):
        """Test that providing no valid fields is a no-op."""
        item = await hitl_service.create_review_item(
            db_session,
            item_type=ReviewItemType.ANOMALY,
            entity_id=uuid.uuid4(),
            entity_type="anomaly_flag",
            title="No change",
        )

        updated = await hitl_service.update_fields(db_session, item.id)
        assert updated.title == "No change"

    @pytest.mark.asyncio
    async def test_update_not_found(self, db_session, hitl_service):
        """Test updating a non-existent item raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            await hitl_service.update_fields(
                db_session, uuid.uuid4(), title="Ghost",
            )

    @pytest.mark.asyncio
    async def test_update_metadata(self, db_session, hitl_service):
        """Test updating review_metadata JSON field."""
        item = await hitl_service.create_review_item(
            db_session,
            item_type=ReviewItemType.ANOMALY,
            entity_id=uuid.uuid4(),
            entity_type="anomaly_flag",
            title="Metadata test",
        )

        updated = await hitl_service.update_fields(
            db_session, item.id,
            review_metadata={"custom_key": "custom_value", "notes": "important"},
        )
        assert updated.review_metadata == {"custom_key": "custom_value", "notes": "important"}


# ── Exception task creation tests ──


class TestExceptionTasks:
    """Tests for exception task creation from review items."""

    @pytest.fixture
    def hitl_service(self):
        settings = MagicMock()
        settings.hitl_auto_approve_dollar_threshold = 1000.0
        settings.hitl_high_risk_dollar_threshold = 10000.0
        return HITLService(settings)

    @pytest.mark.asyncio
    async def test_create_exception_task(self, db_session, hitl_service):
        """Test creating an exception task from a parent review item."""
        parent = await hitl_service.create_review_item(
            db_session,
            item_type=ReviewItemType.RECONCILIATION_MISMATCH,
            entity_id=uuid.uuid4(),
            entity_type="reconciliation_record",
            title="Original mismatch",
            dollar_amount=7500,
        )

        task = await hitl_service.create_exception_task(
            db_session,
            parent_id=parent.id,
            title="Investigate shipment discrepancy",
            description="Amounts differ by 15% — need carrier confirmation",
            assigned_to="ops-team@company.com",
            severity="high",
            created_by="reviewer",
        )

        assert task.id != parent.id
        assert task.item_type == ReviewItemType.EXCEPTION_TASK
        assert task.status == ReviewStatus.PENDING_REVIEW
        assert task.title == "Investigate shipment discrepancy"
        assert task.description == "Amounts differ by 15% — need carrier confirmation"
        assert task.assigned_to == "ops-team@company.com"
        assert task.severity == "high"
        assert task.dollar_amount == 7500  # Inherited from parent
        assert task.auto_approve_eligible is False

    @pytest.mark.asyncio
    async def test_exception_task_metadata(self, db_session, hitl_service):
        """Test exception task metadata contains parent reference."""
        parent = await hitl_service.create_review_item(
            db_session,
            item_type=ReviewItemType.ANOMALY,
            entity_id=uuid.uuid4(),
            entity_type="anomaly_flag",
            title="Parent anomaly",
        )

        task = await hitl_service.create_exception_task(
            db_session,
            parent_id=parent.id,
            title="Follow-up task",
            created_by="admin",
        )

        assert task.review_metadata is not None
        assert task.review_metadata["parent_review_id"] == str(parent.id)
        assert task.review_metadata["parent_title"] == "Parent anomaly"
        assert task.review_metadata["created_by"] == "admin"

    @pytest.mark.asyncio
    async def test_exception_task_inherits_entity(self, db_session, hitl_service):
        """Test exception task inherits entity_id and entity_type from parent."""
        entity_id = uuid.uuid4()
        parent = await hitl_service.create_review_item(
            db_session,
            item_type=ReviewItemType.COST_ALLOCATION,
            entity_id=entity_id,
            entity_type="cost_allocation",
            title="Parent allocation review",
        )

        task = await hitl_service.create_exception_task(
            db_session,
            parent_id=parent.id,
            title="Check GL codes",
        )

        assert task.entity_id == entity_id
        assert task.entity_type == "cost_allocation"

    @pytest.mark.asyncio
    async def test_exception_task_parent_not_found(self, db_session, hitl_service):
        """Test creating exception task with non-existent parent."""
        with pytest.raises(ValueError, match="not found"):
            await hitl_service.create_exception_task(
                db_session,
                parent_id=uuid.uuid4(),
                title="Orphan task",
            )

    @pytest.mark.asyncio
    async def test_exception_task_can_be_reviewed(self, db_session, hitl_service):
        """Test that exception tasks go through normal review lifecycle."""
        parent = await hitl_service.create_review_item(
            db_session,
            item_type=ReviewItemType.ANOMALY,
            entity_id=uuid.uuid4(),
            entity_type="anomaly_flag",
            title="Parent",
        )

        task = await hitl_service.create_exception_task(
            db_session,
            parent_id=parent.id,
            title="Exception to resolve",
        )

        # Approve the exception task
        reviewed = await hitl_service.review_item(
            db_session, task.id, action="approve",
            reviewed_by="resolver", notes="Issue resolved",
        )
        assert reviewed.status == ReviewStatus.APPROVED
        assert reviewed.reviewed_by == "resolver"

    @pytest.mark.asyncio
    async def test_exception_task_appears_in_queue(self, db_session, hitl_service):
        """Test exception tasks show up in the review queue."""
        parent = await hitl_service.create_review_item(
            db_session,
            item_type=ReviewItemType.ANOMALY,
            entity_id=uuid.uuid4(),
            entity_type="anomaly_flag",
            title="Parent",
        )

        await hitl_service.create_exception_task(
            db_session,
            parent_id=parent.id,
            title="Exception in queue",
        )

        items, total = await hitl_service.get_queue(
            db_session, item_type="exception_task",
        )
        assert total >= 1
        assert any(i.item_type == ReviewItemType.EXCEPTION_TASK for i in items)


# ── Reconciliation candidates in context tests ──


class TestReconciliationCandidatesContext:
    """Tests for reconciliation candidates in review context."""

    def test_reconciliation_candidate_schema(self):
        """Test ReconciliationCandidateResponse schema."""
        from app.schemas.review import ReconciliationCandidateResponse

        candidate = ReconciliationCandidateResponse(
            shipment_id="ship-001",
            shipment_ref="SHP-001",
            match_score=0.92,
            status="strong_match",
            match_reasons=["PO match", "Vendor match", "Amount match"],
            diffs=[{"field": "date", "matched": False}],
            has_diffs=True,
        )
        assert candidate.shipment_id == "ship-001"
        assert candidate.match_score == 0.92
        assert len(candidate.match_reasons) == 3
        assert candidate.has_diffs is True

    def test_review_context_with_candidates(self):
        """Test ReviewContext includes reconciliation_candidates."""
        from app.schemas.review import (
            ReconciliationCandidateResponse,
            ReviewContext,
        )

        ctx = ReviewContext(
            anomaly_type="invoice_reconciliation",
            reconciliation_candidates=[
                ReconciliationCandidateResponse(
                    shipment_id="ship-001",
                    match_score=0.92,
                    status="strong_match",
                ),
                ReconciliationCandidateResponse(
                    shipment_id="ship-002",
                    match_score=0.45,
                    status="weak_match",
                ),
            ],
        )
        assert len(ctx.reconciliation_candidates) == 2
        assert ctx.reconciliation_candidates[0].match_score > ctx.reconciliation_candidates[1].match_score

    def test_review_context_empty_candidates_by_default(self):
        """Test reconciliation_candidates defaults to empty list."""
        from app.schemas.review import ReviewContext

        ctx = ReviewContext()
        assert ctx.reconciliation_candidates == []

    def test_suggested_action_schema(self):
        """Test SuggestedAction schema works for invoice reconciliation actions."""
        from app.schemas.review import SuggestedAction

        action = SuggestedAction(
            label="Match Confirmed",
            action="approve",
            notes="Best match is correct",
            variant="success",
        )
        assert action.label == "Match Confirmed"
        assert action.action == "approve"

    def test_review_context_guidance_field(self):
        """Test ReviewContext can hold guidance text."""
        from app.schemas.review import ReviewContext

        ctx = ReviewContext(
            anomaly_type="invoice_reconciliation",
            guidance="Review the ranked candidates below.",
        )
        assert ctx.guidance is not None
        assert "candidates" in ctx.guidance.lower()

    def test_field_update_request_schema(self):
        """Test ReviewFieldUpdateRequest schema."""
        from app.schemas.review import ReviewFieldUpdateRequest

        req = ReviewFieldUpdateRequest(
            title="Updated title",
            assigned_to="team-lead",
            severity="high",
        )
        assert req.title == "Updated title"
        assert req.updated_by == "user"  # default

    def test_exception_task_request_schema(self):
        """Test ExceptionTaskRequest schema."""
        from app.schemas.review import ExceptionTaskRequest

        req = ExceptionTaskRequest(
            title="Investigate discrepancy",
            description="Need to check with carrier",
            assigned_to="ops-team",
            severity="critical",
        )
        assert req.title == "Investigate discrepancy"
        assert req.created_by == "user"  # default

    def test_exception_task_type_in_enum(self):
        """Test EXCEPTION_TASK is a valid ReviewItemType."""
        assert ReviewItemType.EXCEPTION_TASK.value == "exception_task"
