"""
Q&A pipeline — the core RAG orchestrator.

Flow: user question → embed → retrieve top-K chunks → Claude answers with citations.
"""

import json
import logging
import time

import anthropic

from app.config import Settings
from app.rag_engine.embeddings import EmbeddingService
from app.rag_engine.retriever import DocumentRetriever, RetrievedChunk

logger = logging.getLogger("gamma.rag.qa")

QA_SYSTEM_PROMPT = """You are a logistics operations assistant for a freight and warehousing company. Answer questions using ONLY the provided document context. If the context doesn't contain enough information to answer the question, say so clearly — do not make up information.

Always cite which source(s) your answer is based on using [Source N] notation, where N corresponds to the source numbers in the context below.

Be concise and professional. If the question asks about specific numbers (costs, weights, dates), include the exact figures from the documents.

DOCUMENT CONTEXT:
{context}"""


class QAPipeline:
    """Answers questions over logistics documents using RAG."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.model = settings.claude_model
        self.embedding_service = EmbeddingService(settings)
        self.retriever = DocumentRetriever(self.embedding_service)
        self.top_k = settings.rag_top_k
        self.max_context_chars = settings.rag_max_context_chars

    async def answer(self, question: str, db: "AsyncSession") -> "QAResult":
        """Answer a question using retrieved document context.

        Args:
            question: The user's natural language question.
            db: Async database session for vector search.

        Returns:
            QAResult with the answer and source citations.
        """
        start_time = time.monotonic()

        # Step 1: Retrieve relevant chunks
        logger.info("Retrieving chunks for: %s", question[:100])
        chunks = await self.retriever.search(question, db, top_k=self.top_k)

        if not chunks:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            return QAResult(
                answer="I don't have any documents in my knowledge base yet. Please ingest some documents first using the 'Add to Knowledge Base' feature or seed the demo data.",
                chunks=chunks,
                model_used=self.model,
                processing_time_ms=elapsed_ms,
            )

        # Step 2: Build context from chunks (respecting max_context_chars)
        context = self._build_context(chunks)

        # Step 3: Ask Claude
        system_prompt = QA_SYSTEM_PROMPT.format(context=context)

        logger.info("Sending question to Claude with %d source chunks...", len(chunks))
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            temperature=0,
            system=system_prompt,
            messages=[{"role": "user", "content": question}],
        )

        answer_text = response.content[0].text.strip()
        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        logger.info("Q&A complete in %dms", elapsed_ms)

        return QAResult(
            answer=answer_text,
            chunks=chunks,
            model_used=self.model,
            processing_time_ms=elapsed_ms,
        )

    def _build_context(self, chunks: list[RetrievedChunk]) -> str:
        """Build the context string from retrieved chunks, respecting max length."""
        parts = []
        total_chars = 0

        for i, chunk in enumerate(chunks):
            source_label = f"[Source {i + 1}]"
            source_info = f"(Type: {chunk.source_type}"
            if chunk.metadata and chunk.metadata.get("title"):
                source_info += f", Document: {chunk.metadata['title']}"
            source_info += f", Relevance: {chunk.similarity:.2f})"

            entry = f"{source_label} {source_info}\n{chunk.content}\n"

            if total_chars + len(entry) > self.max_context_chars:
                break

            parts.append(entry)
            total_chars += len(entry)

        return "\n".join(parts)


class QAResult:
    """Result from the Q&A pipeline."""

    def __init__(
        self,
        answer: str,
        chunks: list[RetrievedChunk],
        model_used: str,
        processing_time_ms: int,
    ):
        self.answer = answer
        self.chunks = chunks
        self.model_used = model_used
        self.processing_time_ms = processing_time_ms
