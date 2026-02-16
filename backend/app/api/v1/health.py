from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_db
from app.schemas.health import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    # Check database
    db_status = "healthy"
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "unhealthy"

    # Check Redis
    redis_status = "healthy"
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.redis_url)
        await r.ping()
        await r.aclose()
    except Exception:
        redis_status = "unhealthy"

    overall = "healthy" if db_status == "healthy" and redis_status == "healthy" else "degraded"

    return HealthResponse(
        status=overall,
        database=db_status,
        redis=redis_status,
        timestamp=datetime.now(timezone.utc),
        environment=settings.environment,
        version="0.4.0",
    )


@router.get("/metrics")
async def get_metrics(db: AsyncSession = Depends(get_db)) -> dict:
    """Get system metrics: eval scores, HITL stats, processing stats."""
    from sqlalchemy import func as sa_func

    # Latest extraction eval accuracy
    latest_eval = (await db.execute(
        text(
            "SELECT overall_accuracy, model_used, created_at FROM eval_results "
            "WHERE eval_type = 'extraction' ORDER BY created_at DESC LIMIT 1"
        )
    )).first()

    # Latest RAG eval
    latest_rag_eval = (await db.execute(
        text(
            "SELECT overall_accuracy, created_at FROM eval_results "
            "WHERE eval_type = 'rag' ORDER BY created_at DESC LIMIT 1"
        )
    )).first()

    # HITL stats
    from app.models.review import ReviewItem, ReviewStatus
    total_reviews = (await db.execute(
        text("SELECT COUNT(*) FROM review_queue")
    )).scalar() or 0
    approved_reviews = (await db.execute(
        text("SELECT COUNT(*) FROM review_queue WHERE status = 'approved'")
    )).scalar() or 0

    # Anomaly stats
    total_anomalies = (await db.execute(
        text("SELECT COUNT(*) FROM anomaly_flags")
    )).scalar() or 0
    unresolved_anomalies = (await db.execute(
        text("SELECT COUNT(*) FROM anomaly_flags WHERE is_resolved = false")
    )).scalar() or 0

    # Document processing stats
    total_docs = (await db.execute(
        text("SELECT COUNT(*) FROM documents")
    )).scalar() or 0
    extracted_docs = (await db.execute(
        text("SELECT COUNT(*) FROM documents WHERE status = 'extracted'")
    )).scalar() or 0

    return {
        "extraction_eval": {
            "latest_accuracy": latest_eval[0] if latest_eval else None,
            "model_used": latest_eval[1] if latest_eval else None,
            "evaluated_at": latest_eval[2].isoformat() if latest_eval and latest_eval[2] else None,
        },
        "rag_eval": {
            "latest_hit_rate": latest_rag_eval[0] if latest_rag_eval else None,
            "evaluated_at": latest_rag_eval[1].isoformat() if latest_rag_eval and latest_rag_eval[1] else None,
        },
        "hitl": {
            "total_reviews": total_reviews,
            "approved": approved_reviews,
            "approval_rate": round(approved_reviews / max(total_reviews, 1), 3),
        },
        "anomalies": {
            "total": total_anomalies,
            "unresolved": unresolved_anomalies,
        },
        "documents": {
            "total": total_docs,
            "extracted": extracted_docs,
        },
    }
