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


def get_hitl_service():
    from app.hitl_workflow.service import HITLService
    return HITLService(settings)


def get_anomaly_flagger():
    from app.anomaly_flagger.service import AnomalyFlagger
    return AnomalyFlagger(settings)


def get_reconciliation_engine():
    from app.reconciliation_engine.service import ReconciliationEngine
    return ReconciliationEngine(settings)


def get_audit_report_generator():
    from app.audit_generator.report_generator import AuditReportGenerator
    return AuditReportGenerator(settings)


def get_three_way_matching_service():
    from app.matching_engine.service import ThreeWayMatchingService
    return ThreeWayMatchingService()
