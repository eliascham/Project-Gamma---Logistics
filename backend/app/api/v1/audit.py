"""Audit log endpoints — query events, generate reports, view stats."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit_generator.report_generator import AuditReportGenerator
from app.audit_generator.service import AuditService
from app.dependencies import get_audit_report_generator, get_db
from app.schemas.audit import (
    AuditEventListResponse,
    AuditEventResponse,
    AuditReportRequest,
    AuditReportResponse,
    AuditStatsResponse,
)

router = APIRouter()


@router.get("/events", response_model=AuditEventListResponse)
async def list_events(
    entity_type: str | None = None,
    event_type: str | None = None,
    page: int = 1,
    per_page: int = 50,
    db: AsyncSession = Depends(get_db),
) -> AuditEventListResponse:
    """List audit events with optional filtering."""
    events, total = await AuditService.get_events(
        db, entity_type=entity_type, event_type=event_type, page=page, per_page=per_page,
    )
    return AuditEventListResponse(
        events=[AuditEventResponse.model_validate(e) for e in events],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.post("/reports", response_model=AuditReportResponse)
async def generate_report(
    request: AuditReportRequest,
    db: AsyncSession = Depends(get_db),
    generator: AuditReportGenerator = Depends(get_audit_report_generator),
) -> AuditReportResponse:
    """Generate a Claude-powered audit report."""
    result = await generator.generate_report(
        db,
        start_date=request.start_date,
        end_date=request.end_date,
        entity_type=request.entity_type,
    )
    return AuditReportResponse(**result)


@router.get("/stats", response_model=AuditStatsResponse)
async def get_stats(
    db: AsyncSession = Depends(get_db),
) -> AuditStatsResponse:
    """Get audit event statistics."""
    stats = await AuditService.get_stats(db)
    return AuditStatsResponse(
        total_events=stats["total_events"],
        events_by_type=stats["events_by_type"],
        events_by_actor_type=stats["events_by_actor_type"],
        recent_events=[AuditEventResponse.model_validate(e) for e in stats["recent_events"]],
    )
