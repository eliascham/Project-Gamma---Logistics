"""RAG retrieval quality evaluation.

Curated Q&A benchmark with expected answers and expected source documents.
Metrics: hit rate, MRR (mean reciprocal rank), answer accuracy, negative rejection rate.

Benchmark questions are loaded from ground_truth/rag_benchmark.json. Falls back to
a legacy hardcoded list if the file is missing.
"""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from app.config import Settings
from app.rag_engine.qa import QAPipeline

# Voyage AI free tier: 3 RPM — wait 21s between calls to stay under limit
DEFAULT_RATE_LIMIT_DELAY = 21

logger = logging.getLogger("gamma.eval.rag")

# Hedging phrases that indicate the model correctly declined to answer
_DECLINE_PHRASES = [
    "i don't have", "i do not have",
    "not available", "not found",
    "cannot find", "can't find",
    "no information", "don't have enough",
    "not in the", "not contained",
    "outside", "beyond",
    "i'm unable", "i am unable",
]

# Legacy fallback (used only if rag_benchmark.json is missing)
_LEGACY_BENCHMARK = [
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


def _load_benchmark(benchmark_file: str | None = None) -> list[dict]:
    """Load benchmark questions from JSON file or fall back to legacy list."""
    if benchmark_file is None:
        benchmark_file = str(Path(__file__).parent / "ground_truth" / "rag_benchmark.json")

    path = Path(benchmark_file)
    if path.exists():
        try:
            with open(path) as f:
                data = json.load(f)
            return data.get("benchmark", _LEGACY_BENCHMARK)
        except (json.JSONDecodeError, OSError):
            logger.warning("Failed to load %s, using legacy benchmark", benchmark_file)

    return _LEGACY_BENCHMARK


@dataclass
class RAGEvalResult:
    """Result for a single benchmark question."""
    question: str
    answer: str | None = None
    sources_found: list[str] = field(default_factory=list)
    hit: bool = False
    reciprocal_rank: float = 0.0
    answer_contains_expected: bool = False
    is_negative: bool = False
    correctly_declined: bool = False
    category: str = ""
    error: str | None = None


@dataclass
class RAGEvalReport:
    """Complete RAG evaluation report."""
    eval_id: str = ""
    results: list[RAGEvalResult] = field(default_factory=list)
    hit_rate: float = 0.0
    mrr: float = 0.0
    answer_accuracy: float = 0.0
    negative_rejection_rate: float = 0.0
    per_category_accuracy: dict[str, float] = field(default_factory=dict)
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
            "negative_rejection_rate": round(self.negative_rejection_rate, 4),
            "per_category_accuracy": {
                k: round(v, 4) for k, v in self.per_category_accuracy.items()
            },
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
                    "is_negative": r.is_negative,
                    "correctly_declined": r.correctly_declined,
                    "category": r.category,
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

    async def run(
        self,
        db,
        rate_limit_delay: float = DEFAULT_RATE_LIMIT_DELAY,
        benchmark_file: str | None = None,
    ) -> RAGEvalReport:
        """Run the RAG evaluation benchmark.

        Args:
            db: AsyncSession for database queries.
            rate_limit_delay: Seconds to wait between questions to respect
                Voyage AI rate limits. Set to 0 for paid plans with higher RPM.
            benchmark_file: Path to benchmark JSON file. Defaults to
                ground_truth/rag_benchmark.json.
        """
        start = time.monotonic()
        eval_id = str(uuid.uuid4())[:8]

        benchmark = _load_benchmark(benchmark_file)

        report = RAGEvalReport(
            eval_id=eval_id,
            total_questions=len(benchmark),
            model_used=self.settings.claude_model,
        )

        hits = []
        rrs = []
        answer_matches = []
        negative_results = []

        # Per-category tracking
        category_correct: dict[str, int] = {}
        category_total: dict[str, int] = {}

        for i, bench in enumerate(benchmark):
            # Rate-limit: wait between questions (skip first)
            if i > 0 and rate_limit_delay > 0:
                logger.info(
                    "RAG eval: waiting %.0fs for rate limit (%d/%d)...",
                    rate_limit_delay, i + 1, len(benchmark),
                )
                await asyncio.sleep(rate_limit_delay)

            logger.info("RAG eval: question %d/%d — %s", i + 1, len(benchmark), bench["question"])

            is_negative = bench.get("is_negative", False)
            category = bench.get("category", "")

            try:
                result = await self.pipeline.answer(bench["question"], db)

                # Collect source identifiers
                source_ids = []
                for chunk in result.chunks:
                    if chunk.metadata:
                        title = chunk.metadata.get("title", "")
                        if title:
                            source_ids.append(title.lower().replace(" ", "_"))

                if is_negative:
                    # Negative test: check if model correctly declined
                    answer_lower = result.answer.lower()
                    declined = any(
                        phrase in answer_lower for phrase in _DECLINE_PHRASES
                    )
                    negative_results.append(declined)

                    report.results.append(RAGEvalResult(
                        question=bench["question"],
                        answer=result.answer[:500],
                        sources_found=source_ids,
                        is_negative=True,
                        correctly_declined=declined,
                        category=category,
                    ))

                    # Category tracking
                    category_total[category] = category_total.get(category, 0) + 1
                    if declined:
                        category_correct[category] = category_correct.get(category, 0) + 1
                else:
                    # Positive test: standard evaluation
                    expected_sources = [s.lower() for s in bench["expected_sources"]]
                    hit = any(
                        any(exp in src for exp in expected_sources)
                        for src in source_ids
                    )

                    # Compute reciprocal rank
                    rr = 0.0
                    for j, src in enumerate(source_ids):
                        if any(exp in src for exp in expected_sources):
                            rr = 1.0 / (j + 1)
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
                        category=category,
                    ))

                    # Category tracking
                    category_total[category] = category_total.get(category, 0) + 1
                    if contains:
                        category_correct[category] = category_correct.get(category, 0) + 1

                report.successful_questions += 1

            except Exception as e:
                logger.error("RAG eval failed for: %s — %s", bench["question"], e)
                report.results.append(RAGEvalResult(
                    question=bench["question"],
                    is_negative=is_negative,
                    category=category,
                    error=str(e),
                ))

        # Compute aggregate metrics (positive questions only)
        if hits:
            report.hit_rate = sum(1 for h in hits if h) / len(hits)
        if rrs:
            report.mrr = sum(rrs) / len(rrs)
        if answer_matches:
            report.answer_accuracy = sum(1 for m in answer_matches if m) / len(answer_matches)

        # Negative rejection rate
        if negative_results:
            report.negative_rejection_rate = (
                sum(1 for r in negative_results if r) / len(negative_results)
            )

        # Per-category accuracy
        for cat, total in category_total.items():
            correct = category_correct.get(cat, 0)
            report.per_category_accuracy[cat] = correct / total if total > 0 else 0.0

        report.elapsed_ms = int((time.monotonic() - start) * 1000)

        logger.info(
            "RAG eval complete: hit_rate=%.2f%%, MRR=%.3f, answer_accuracy=%.2f%%, "
            "negative_rejection=%.2f%%, %dms",
            report.hit_rate * 100, report.mrr, report.answer_accuracy * 100,
            report.negative_rejection_rate * 100, report.elapsed_ms,
        )

        return report
