from fastapi import APIRouter

from app.api.v1 import allocations, documents, eval, extractions, health, rag

api_router = APIRouter()

api_router.include_router(health.router, prefix="/v1", tags=["health"])
api_router.include_router(documents.router, prefix="/v1/documents", tags=["documents"])
api_router.include_router(extractions.router, prefix="/v1/extractions", tags=["extractions"])
api_router.include_router(eval.router, prefix="/v1/eval", tags=["eval"])
api_router.include_router(allocations.router, prefix="/v1/allocations", tags=["allocations"])
api_router.include_router(rag.router, prefix="/v1/rag", tags=["rag"])
