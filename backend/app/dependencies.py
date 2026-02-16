from app.config import settings
from app.cost_allocator.pipeline import CostAllocationPipeline
from app.database import get_db
from app.rag_engine.ingest import RAGIngestor
from app.rag_engine.qa import QAPipeline
from app.services.claude_service import ClaudeService

# Re-export get_db for use in Depends()
get_db = get_db


def get_claude_service() -> ClaudeService:
    return ClaudeService(settings)


def get_cost_allocation_pipeline() -> CostAllocationPipeline:
    return CostAllocationPipeline(settings)


def get_qa_pipeline() -> QAPipeline:
    return QAPipeline(settings)


def get_rag_ingestor() -> RAGIngestor:
    return RAGIngestor(settings)
