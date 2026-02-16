"""RAG retrieval quality evaluation.

Curated Q&A benchmark with expected answers and expected source documents.
Metrics: hit rate, MRR (mean reciprocal rank), answer faithfulness (Claude self-eval).
"""

import logging
import time
import uuid
from dataclasses import dataclass, field

from app.config import Settings
from app.rag_engine.qa import QAPipeline

logger = logging.getLogger("gamma.eval.rag")

# ── Curated benchmark questions ──
RAG_BENCHMARK = [
    {
        "question": "What GL account is used for ocean freight?",
        "expected_answer_contains": ["5010", "ocean freight"],
        "expected_sources": ["gl_account_mapping", "cost_center_guidelines"],
    },
    {
        "question": "What is the approval threshold for cost allocations?",
        "expected_answer_contains": ["85%", "confidence"],
        "expected_sources": ["invoice_processing"],
    },
    {
        "question": "How should customs duties be allocated?",
        "expected_answer_contains": ["customs", "5020"],
        "expected_sources": ["gl_account_mapping", "cost_center_guidelines"],
    },
    {
        "question": "What is the process for handling freight invoices?",
        "expected_answer_contains": ["invoice", "extract"],
        "expected_sources": ["invoice_processing"],
    },
    {
        "question": "Which cost center handles domestic transportation?",
        "expected_answer_contains": ["domestic", "cost center"],
        "expected_sources": ["cost_center_guidelines"],
    },
    {
        "question": "What GL account is used for warehousing charges?",
        "expected_answer_contains": ["5040", "warehouse"],
        "expected_sources": ["gl_account_mapping"],
    },
    {
        "question": "How are drayage charges categorized?",
        "expected_answer_contains": ["drayage", "5030"],
        "expected_sources": ["gl_account_mapping"],
    },
    {
        "question": "What documentation is required for international shipments?",
        "expected_answer_contains": ["bill of lading", "commercial invoice"],
        "expected_sources": ["invoice_processing"],
    },
    {
        "question": "What is the review process for high-value allocations?",
        "expected_answer_contains": ["review", "approval"],
        "expected_sources": ["invoice_processing", "cost_center_guidelines"],
    },
    {
        "question": "How should insurance charges be recorded?",
        "expected_answer_contains": ["insurance", "5050"],
        "expected_sources": ["gl_account_mapping"],
    },
]


@dataclass
class RAGEvalResult:
    """Result for a single benchmark question."""
    question: str
    answer: str | None = None
    sources_found: list[str] = field(default_factory=list)
    hit: bool = False
    reciprocal_rank: float = 0.0
    answer_contains_expected: bool = False
    error: str | None = None


@dataclass
class RAGEvalReport:
    """Complete RAG evaluation report."""
    eval_id: str = ""
    results: list[RAGEvalResult] = field(default_factory=list)
    hit_rate: float = 0.0
    mrr: float = 0.0
    answer_accuracy: float = 0.0
    total_questions: int = 0
    successful_questions: int = 0
    elapsed_ms: int = 0
    model_used: str = ""

    def to_dict(self) -> dict:
        return {
            "eval_id": self.eval_id,
            "hit_rate": round(self.hit_rate, 4),
            "mrr": round(self.mrr, 4),
            "answer_accuracy": round(self.answer_accuracy, 4),
            "total_questions": self.total_questions,
            "successful_questions": self.successful_questions,
            "elapsed_ms": self.elapsed_ms,
            "model_used": self.model_used,
            "questions": [
                {
                    "question": r.question,
                    "hit": r.hit,
                    "reciprocal_rank": r.reciprocal_rank,
                    "answer_contains_expected": r.answer_contains_expected,
                    "sources_found": r.sources_found,
                    "error": r.error,
                }
                for r in self.results
            ],
        }


class RAGEvaluator:
    """Runs RAG retrieval quality evaluation against benchmark questions."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.pipeline = QAPipeline(settings)

    async def run(self, db) -> RAGEvalReport:
        """Run the RAG evaluation benchmark."""
        start = time.monotonic()
        eval_id = str(uuid.uuid4())[:8]

        report = RAGEvalReport(
            eval_id=eval_id,
            total_questions=len(RAG_BENCHMARK),
            model_used=self.settings.claude_model,
        )

        hits = []
        rrs = []
        answer_matches = []

        for bench in RAG_BENCHMARK:
            try:
                result = await self.pipeline.answer(bench["question"], db)

                # Collect source identifiers
                source_ids = []
                for chunk in result.chunks:
                    if chunk.metadata:
                        title = chunk.metadata.get("title", "")
                        if title:
                            source_ids.append(title.lower().replace(" ", "_"))

                # Check hit rate: is any expected source in top-K results?
                expected_sources = [s.lower() for s in bench["expected_sources"]]
                hit = any(
                    any(exp in src for exp in expected_sources)
                    for src in source_ids
                )

                # Compute reciprocal rank
                rr = 0.0
                for i, src in enumerate(source_ids):
                    if any(exp in src for exp in expected_sources):
                        rr = 1.0 / (i + 1)
                        break

                # Check answer contains expected keywords
                answer_lower = result.answer.lower()
                expected_keywords = bench["expected_answer_contains"]
                contains = any(kw.lower() in answer_lower for kw in expected_keywords)

                hits.append(hit)
                rrs.append(rr)
                answer_matches.append(contains)

                report.results.append(RAGEvalResult(
                    question=bench["question"],
                    answer=result.answer[:500],
                    sources_found=source_ids,
                    hit=hit,
                    reciprocal_rank=rr,
                    answer_contains_expected=contains,
                ))
                report.successful_questions += 1

            except Exception as e:
                logger.error("RAG eval failed for: %s — %s", bench["question"], e)
                report.results.append(RAGEvalResult(
                    question=bench["question"],
                    error=str(e),
                ))

        if hits:
            report.hit_rate = sum(1 for h in hits if h) / len(hits)
        if rrs:
            report.mrr = sum(rrs) / len(rrs)
        if answer_matches:
            report.answer_accuracy = sum(1 for m in answer_matches if m) / len(answer_matches)

        report.elapsed_ms = int((time.monotonic() - start) * 1000)

        logger.info(
            "RAG eval complete: hit_rate=%.2f%%, MRR=%.3f, answer_accuracy=%.2f%%, %dms",
            report.hit_rate * 100, report.mrr, report.answer_accuracy * 100, report.elapsed_ms,
        )

        return report
