"""Anomaly detection endpoints — scan, list, resolve, stats, audit summary."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.anomaly_flagger.service import AnomalyFlagger
from app.audit_generator.service import AuditService
from app.dependencies import get_anomaly_flagger, get_db
from app.models.anomaly import AnomalyFlag, AnomalySeverity, AnomalyType
from app.schemas.anomaly import (
    AnomalyAuditSummaryResponse,
    AnomalyFlagListResponse,
    AnomalyFlagResponse,
    AnomalyResolutionRequest,
    AnomalyScanRequest,
    AnomalyStatsResponse,
)

router = APIRouter()


@router.post("/scan")
async def scan_anomalies(
    request: AnomalyScanRequest,
    db: AsyncSession = Depends(get_db),
    flagger: AnomalyFlagger = Depends(get_anomaly_flagger),
) -> dict:
    """Run anomaly detection on a document or all recent allocations."""
    anomalies = await flagger.scan(db, document_id=request.document_id)
    return {
        "anomalies_found": len(anomalies),
        "anomaly_ids": [str(a.id) for a in anomalies],
    }


@router.get("/list", response_model=AnomalyFlagListResponse)
async def list_anomalies(
    anomaly_type: str | None = None,
    severity: str | None = None,
    is_resolved: bool | None = None,
    page: int = 1,
    per_page: int = 20,
    db: AsyncSession = Depends(get_db),
) -> AnomalyFlagListResponse:
    """List anomaly flags with filtering."""
    query = select(AnomalyFlag)
    count_query = select(func.count(AnomalyFlag.id))

    if anomaly_type:
        query = query.where(AnomalyFlag.anomaly_type == anomaly_type)
        count_query = count_query.where(AnomalyFlag.anomaly_type == anomaly_type)
    if severity:
        query = query.where(AnomalyFlag.severity == severity)
        count_query = count_query.where(AnomalyFlag.severity == severity)
    if is_resolved is not None:
        query = query.where(AnomalyFlag.is_resolved == is_resolved)
        count_query = count_query.where(AnomalyFlag.is_resolved == is_resolved)

    total = (await db.execute(count_query)).scalar_one()

    offset = (page - 1) * per_page
    query = query.order_by(AnomalyFlag.created_at.desc()).offset(offset).limit(per_page)
    result = await db.execute(query)
    anomalies = list(result.scalars().all())

    return AnomalyFlagListResponse(
        anomalies=[_anomaly_to_response(a) for a in anomalies],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/stats", response_model=AnomalyStatsResponse)
async def get_stats(
    db: AsyncSession = Depends(get_db),
) -> AnomalyStatsResponse:
    """Get anomaly statistics."""
    total = (await db.execute(select(func.count(AnomalyFlag.id)))).scalar_one()
    unresolved = (await db.execute(
        select(func.count(AnomalyFlag.id)).where(AnomalyFlag.is_resolved == False)  # noqa: E712
    )).scalar_one()

    by_type_rows = (await db.execute(
        select(AnomalyFlag.anomaly_type, func.count(AnomalyFlag.id))
        .group_by(AnomalyFlag.anomaly_type)
    )).all()
    by_type = {
        (r[0].value if isinstance(r[0], AnomalyType) else r[0]): r[1]
        for r in by_type_rows
    }

    by_sev_rows = (await db.execute(
        select(AnomalyFlag.severity, func.count(AnomalyFlag.id))
        .group_by(AnomalyFlag.severity)
    )).all()
    by_severity = {
        (r[0].value if isinstance(r[0], AnomalySeverity) else r[0]): r[1]
        for r in by_sev_rows
    }

    return AnomalyStatsResponse(
        total=total,
        unresolved=unresolved,
        by_type=by_type,
        by_severity=by_severity,
    )


@router.get("/{anomaly_id}", response_model=AnomalyFlagResponse)
async def get_anomaly(
    anomaly_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> AnomalyFlagResponse:
    """Get a specific anomaly flag."""
    result = await db.execute(select(AnomalyFlag).where(AnomalyFlag.id == anomaly_id))
    anomaly = result.scalar_one_or_none()
    if anomaly is None:
        raise HTTPException(status_code=404, detail="Anomaly not found")
    return _anomaly_to_response(anomaly)


@router.post("/{anomaly_id}/resolve", response_model=AnomalyFlagResponse)
async def resolve_anomaly(
    anomaly_id: uuid.UUID,
    request: AnomalyResolutionRequest,
    db: AsyncSession = Depends(get_db),
) -> AnomalyFlagResponse:
    """Resolve an anomaly flag."""
    result = await db.execute(select(AnomalyFlag).where(AnomalyFlag.id == anomaly_id))
    anomaly = result.scalar_one_or_none()
    if anomaly is None:
        raise HTTPException(status_code=404, detail="Anomaly not found")

    anomaly.is_resolved = True
    anomaly.resolved_by = request.resolved_by
    anomaly.resolved_at = datetime.now(timezone.utc)
    anomaly.resolution_notes = request.resolution_notes
    await db.flush()

    await AuditService.log_event(
        db,
        event_type="ANOMALY_RESOLVED",
        entity_type="anomaly_flag",
        entity_id=anomaly.id,
        action="resolve",
        actor=request.resolved_by,
        actor_type="user",
        new_state={"is_resolved": True, "resolution_notes": request.resolution_notes},
    )

    return _anomaly_to_response(anomaly)


@router.post("/audit-summary", response_model=AnomalyAuditSummaryResponse)
async def generate_audit_summary(
    db: AsyncSession = Depends(get_db),
    flagger: AnomalyFlagger = Depends(get_anomaly_flagger),
) -> AnomalyAuditSummaryResponse:
    """Generate a Claude-powered audit summary of anomalies."""
    result = await flagger.generate_audit_summary(db)
    return AnomalyAuditSummaryResponse(**result)


def _anomaly_to_response(anomaly: AnomalyFlag) -> AnomalyFlagResponse:
    return AnomalyFlagResponse(
        id=anomaly.id,
        document_id=anomaly.document_id,
        allocation_id=anomaly.allocation_id,
        anomaly_type=anomaly.anomaly_type.value if isinstance(anomaly.anomaly_type, AnomalyType) else anomaly.anomaly_type,
        severity=anomaly.severity.value if isinstance(anomaly.severity, AnomalySeverity) else anomaly.severity,
        title=anomaly.title,
        description=anomaly.description,
        details=anomaly.details,
        is_resolved=anomaly.is_resolved,
        resolved_by=anomaly.resolved_by,
        resolved_at=anomaly.resolved_at,
        resolution_notes=anomaly.resolution_notes,
        review_item_id=anomaly.review_item_id,
        created_at=anomaly.created_at,
    )
