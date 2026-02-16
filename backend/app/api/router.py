from fastapi import APIRouter

from app.api.v1 import (
    allocations,
    anomalies,
    audit,
    documents,
    eval,
    extractions,
    health,
    mcp_status,
    rag,
    reconciliation,
    reviews,
)

api_router = APIRouter()

api_router.include_router(health.router, prefix="/v1", tags=["health"])
api_router.include_router(documents.router, prefix="/v1/documents", tags=["documents"])
api_router.include_router(extractions.router, prefix="/v1/extractions", tags=["extractions"])
api_router.include_router(eval.router, prefix="/v1/eval", tags=["eval"])
api_router.include_router(allocations.router, prefix="/v1/allocations", tags=["allocations"])
api_router.include_router(rag.router, prefix="/v1/rag", tags=["rag"])
api_router.include_router(audit.router, prefix="/v1/audit", tags=["audit"])
api_router.include_router(reviews.router, prefix="/v1/reviews", tags=["reviews"])
api_router.include_router(anomalies.router, prefix="/v1/anomalies", tags=["anomalies"])
api_router.include_router(reconciliation.router, prefix="/v1/reconciliation", tags=["reconciliation"])
api_router.include_router(mcp_status.router, prefix="/v1/mcp", tags=["mcp"])
