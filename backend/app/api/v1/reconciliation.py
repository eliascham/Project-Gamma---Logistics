"""Reconciliation engine endpoints — run, seed, list, detail, stats."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.dependencies import get_db, get_reconciliation_engine
from app.models.reconciliation import (
    ReconciliationRecord,
    ReconciliationRun,
    ReconciliationStatus,
    RecordSource,
)
from app.reconciliation_engine.service import ReconciliationEngine
from app.schemas.reconciliation import (
    ReconciliationRecordResponse,
    ReconciliationRunListResponse,
    ReconciliationRunResponse,
    ReconciliationStatsResponse,
    ReconciliationTriggerRequest,
)

router = APIRouter()


@router.post("/run", response_model=ReconciliationRunResponse)
async def run_reconciliation(
    request: ReconciliationTriggerRequest,
    db: AsyncSession = Depends(get_db),
    engine: ReconciliationEngine = Depends(get_reconciliation_engine),
) -> ReconciliationRunResponse:
    """Run a reconciliation pass across TMS/WMS/ERP data."""
    run = await engine.run_reconciliation(
        db, name=request.name, description=request.description, run_by=request.run_by,
    )
    return _run_to_response(run)


@router.post("/seed")
async def seed_mock_data(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Seed mock logistics data for reconciliation testing."""
    from app.mcp_server.mock_data import MockDataGenerator
    gen = MockDataGenerator(seed=42)
    counts = await gen.seed_all(db)
    return {"message": "Mock data seeded", **counts}


@router.get("/runs", response_model=ReconciliationRunListResponse)
async def list_runs(
    page: int = 1,
    per_page: int = 20,
    db: AsyncSession = Depends(get_db),
) -> ReconciliationRunListResponse:
    """List reconciliation runs."""
    total = (await db.execute(select(func.count(ReconciliationRun.id)))).scalar_one()
    offset = (page - 1) * per_page
    result = await db.execute(
        select(ReconciliationRun)
        .order_by(ReconciliationRun.created_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    runs = list(result.scalars().all())

    return ReconciliationRunListResponse(
        runs=[_run_to_response(r, include_records=False) for r in runs],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/stats", response_model=ReconciliationStatsResponse)
async def get_stats(
    db: AsyncSession = Depends(get_db),
) -> ReconciliationStatsResponse:
    """Get reconciliation statistics."""
    total_runs = (await db.execute(select(func.count(ReconciliationRun.id)))).scalar_one()
    total_records = (await db.execute(select(func.count(ReconciliationRecord.id)))).scalar_one()

    avg_match_rate = (await db.execute(
        select(func.avg(ReconciliationRun.match_rate))
    )).scalar()

    last_run = (await db.execute(
        select(ReconciliationRun.created_at)
        .order_by(ReconciliationRun.created_at.desc())
        .limit(1)
    )).scalar()

    return ReconciliationStatsResponse(
        total_runs=total_runs,
        total_records=total_records,
        avg_match_rate=round(avg_match_rate, 4) if avg_match_rate else None,
        last_run_at=last_run,
    )


@router.get("/{run_id}", response_model=ReconciliationRunResponse)
async def get_run(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ReconciliationRunResponse:
    """Get a reconciliation run with its records."""
    result = await db.execute(
        select(ReconciliationRun)
        .options(selectinload(ReconciliationRun.records))
        .where(ReconciliationRun.id == run_id)
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Reconciliation run not found")

    return _run_to_response(run)


def _run_to_response(run: ReconciliationRun, include_records: bool = True) -> ReconciliationRunResponse:
    records = []
    if include_records and hasattr(run, "records") and run.records:
        records = [
            ReconciliationRecordResponse(
                id=r.id,
                run_id=r.run_id,
                source=r.source.value if isinstance(r.source, RecordSource) else r.source,
                record_type=r.record_type,
                reference_number=r.reference_number,
                record_data=r.record_data,
                match_status=r.match_status.value if isinstance(r.match_status, ReconciliationStatus) else r.match_status,
                matched_with_id=r.matched_with_id,
                match_confidence=r.match_confidence,
                match_reasoning=r.match_reasoning,
                mismatch_details=r.mismatch_details,
                created_at=r.created_at,
            )
            for r in run.records
        ]

    return ReconciliationRunResponse(
        id=run.id,
        name=run.name,
        description=run.description,
        status=run.status.value if isinstance(run.status, ReconciliationStatus) else run.status,
        total_records=run.total_records,
        matched_count=run.matched_count,
        mismatch_count=run.mismatch_count,
        match_rate=run.match_rate,
        run_by=run.run_by,
        model_used=run.model_used,
        processing_time_ms=run.processing_time_ms,
        summary=run.summary,
        records=records,
        created_at=run.created_at,
    )
