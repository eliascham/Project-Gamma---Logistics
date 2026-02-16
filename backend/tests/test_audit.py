"""Tests for AuditService and audit endpoints."""

import uuid

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.audit_generator.service import AuditService
from app.models.audit import AuditEvent


class TestAuditService:
    """Tests for AuditService static methods."""

    @pytest.mark.asyncio
    async def test_log_event(self, db_session):
        """Test creating an audit event."""
        event = await AuditService.log_event(
            db_session,
            event_type="DOCUMENT_UPLOADED",
            entity_type="document",
            entity_id=uuid.uuid4(),
            action="upload",
            actor="user",
            actor_type="user",
            new_state={"filename": "test.csv"},
        )

        assert event.id is not None
        assert event.event_type == "DOCUMENT_UPLOADED"
        assert event.entity_type == "document"
        assert event.actor == "user"
        assert event.actor_type == "user"
        assert event.new_state == {"filename": "test.csv"}

    @pytest.mark.asyncio
    async def test_log_event_minimal(self, db_session):
        """Test creating an audit event with minimal fields."""
        event = await AuditService.log_event(
            db_session,
            event_type="TEST_EVENT",
        )

        assert event.event_type == "TEST_EVENT"
        assert event.actor == "system"
        assert event.actor_type == "system"

    @pytest.mark.asyncio
    async def test_get_events_empty(self, db_session):
        """Test querying events when none exist."""
        events, total = await AuditService.get_events(db_session)
        assert total == 0
        assert events == []

    @pytest.mark.asyncio
    async def test_get_events_with_data(self, db_session):
        """Test querying events after logging some."""
        for i in range(3):
            await AuditService.log_event(
                db_session,
                event_type=f"EVENT_{i}",
                entity_type="test",
            )

        events, total = await AuditService.get_events(db_session)
        assert total == 3
        assert len(events) == 3

    @pytest.mark.asyncio
    async def test_get_events_filtered_by_entity_type(self, db_session):
        """Test filtering events by entity_type."""
        await AuditService.log_event(db_session, event_type="A", entity_type="document")
        await AuditService.log_event(db_session, event_type="B", entity_type="allocation")
        await AuditService.log_event(db_session, event_type="C", entity_type="document")

        events, total = await AuditService.get_events(
            db_session, entity_type="document"
        )
        assert total == 2
        assert all(e.entity_type == "document" for e in events)

    @pytest.mark.asyncio
    async def test_get_events_filtered_by_event_type(self, db_session):
        """Test filtering events by event_type."""
        await AuditService.log_event(db_session, event_type="UPLOAD")
        await AuditService.log_event(db_session, event_type="EXTRACT")
        await AuditService.log_event(db_session, event_type="UPLOAD")

        events, total = await AuditService.get_events(
            db_session, event_type="UPLOAD"
        )
        assert total == 2

    @pytest.mark.asyncio
    async def test_get_events_pagination(self, db_session):
        """Test pagination of events."""
        for i in range(5):
            await AuditService.log_event(db_session, event_type=f"EVT_{i}")

        page1, total = await AuditService.get_events(db_session, page=1, per_page=2)
        assert total == 5
        assert len(page1) == 2

        page2, _ = await AuditService.get_events(db_session, page=2, per_page=2)
        assert len(page2) == 2

        page3, _ = await AuditService.get_events(db_session, page=3, per_page=2)
        assert len(page3) == 1

    @pytest.mark.asyncio
    async def test_get_stats(self, db_session):
        """Test getting audit stats."""
        await AuditService.log_event(db_session, event_type="A", actor_type="user")
        await AuditService.log_event(db_session, event_type="B", actor_type="ai")
        await AuditService.log_event(db_session, event_type="A", actor_type="user")

        stats = await AuditService.get_stats(db_session)
        assert stats["total_events"] == 3
        assert stats["events_by_type"]["A"] == 2
        assert stats["events_by_type"]["B"] == 1
        assert stats["events_by_actor_type"]["user"] == 2
        assert stats["events_by_actor_type"]["ai"] == 1
        assert len(stats["recent_events"]) == 3
