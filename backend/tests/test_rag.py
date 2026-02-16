"""Tests for the RAG engine: chunking, text conversion, and Q&A pipeline."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.rag_engine.chunker import chunk_text, extraction_to_text
from app.rag_engine.qa import QAPipeline


class TestChunker:
    """Tests for text chunking utilities."""

    def test_short_text_single_chunk(self):
        """Text shorter than chunk_size returns a single chunk."""
        result = chunk_text("Short text", chunk_size=500)
        assert result == ["Short text"]

    def test_empty_text(self):
        """Empty text returns empty list."""
        assert chunk_text("") == []
        assert chunk_text("   ") == []

    def test_long_text_multiple_chunks(self):
        """Long text is split into multiple overlapping chunks."""
        text = "A" * 1200
        chunks = chunk_text(text, chunk_size=500, overlap=50)
        assert len(chunks) >= 2
        # Verify total coverage
        assert all(len(c) > 0 for c in chunks)

    def test_sentence_boundary_splitting(self):
        """Chunks should prefer breaking at sentence boundaries."""
        text = "First sentence. Second sentence. Third sentence. Fourth sentence. " * 10
        chunks = chunk_text(text, chunk_size=100, overlap=20)
        assert len(chunks) >= 2
        # Most chunks should end at a period
        for chunk in chunks[:-1]:  # last chunk can end anywhere
            assert "." in chunk

    def test_overlap(self):
        """Verify chunks overlap as expected."""
        text = "word " * 200
        chunks = chunk_text(text, chunk_size=100, overlap=20)
        assert len(chunks) >= 2


class TestExtractionToText:
    """Tests for converting structured extractions to natural language."""

    def test_freight_invoice_to_text(self):
        """Test freight invoice conversion."""
        extraction = {
            "invoice_number": "FI-2024-001",
            "vendor_name": "Test Freight LLC",
            "invoice_date": "2024-12-01",
            "origin": "Shanghai",
            "destination": "Los Angeles",
            "currency": "USD",
            "line_items": [
                {"description": "Ocean Freight", "quantity": 1, "unit": "container",
                 "unit_price": 2500, "total": 2500},
            ],
            "total_amount": 2500.0,
        }
        result = extraction_to_text(extraction, "freight_invoice")
        assert "FI-2024-001" in result
        assert "Test Freight LLC" in result
        assert "Ocean Freight" in result
        assert "2500" in result

    def test_bol_to_text(self):
        """Test bill of lading conversion."""
        extraction = {
            "bol_number": "BOL-001",
            "issue_date": "2024-12-01",
            "carrier_name": "Maersk",
            "vessel_name": "MSC Divina",
            "shipper": {"name": "Shipper Corp"},
            "consignee": {"name": "Consignee Ltd"},
            "origin": {"port": "Shanghai", "country": "China"},
            "destination": {"port": "Long Beach", "country": "USA"},
            "cargo_description": "Electronics",
            "container_numbers": ["MSKU1234567"],
        }
        result = extraction_to_text(extraction, "bill_of_lading")
        assert "BOL-001" in result
        assert "Maersk" in result
        assert "Electronics" in result
        assert "MSKU1234567" in result

    def test_unknown_doc_type(self):
        """Test fallback for unknown doc types."""
        extraction = {"field_a": "value_a", "field_b": 42}
        result = extraction_to_text(extraction, "unknown")
        assert "value_a" in result
        assert "42" in result


class TestQAPipeline:
    """Tests for the Q&A pipeline."""

    @pytest.fixture
    def mock_settings(self):
        settings = MagicMock()
        settings.anthropic_api_key = "test-key"
        settings.claude_model = "claude-sonnet-4-20250514"
        settings.voyage_api_key = "test-voyage-key"
        settings.voyage_model = "voyage-3"
        settings.rag_top_k = 3
        settings.rag_max_context_chars = 4000
        return settings

    @pytest.mark.asyncio
    async def test_answer_no_chunks(self, mock_settings):
        """Test Q&A when no chunks are found — should return helpful message."""
        pipeline = QAPipeline(mock_settings)
        pipeline.retriever = AsyncMock()
        pipeline.retriever.search = AsyncMock(return_value=[])

        mock_db = AsyncMock()
        result = await pipeline.answer("What is the freight cost?", mock_db)

        assert "don't have any documents" in result.answer
        assert result.chunks == []

    @pytest.mark.asyncio
    async def test_answer_with_chunks(self, mock_settings):
        """Test Q&A with retrieved chunks — should call Claude."""
        pipeline = QAPipeline(mock_settings)

        # Mock retriever
        from app.rag_engine.retriever import RetrievedChunk
        mock_chunks = [
            RetrievedChunk(
                embedding_id="1",
                document_id="doc-1",
                content="Ocean freight from Shanghai costs $2500 per container.",
                source_type="extraction",
                metadata={"title": "invoice.csv"},
                similarity=0.92,
            ),
        ]
        pipeline.retriever = AsyncMock()
        pipeline.retriever.search = AsyncMock(return_value=mock_chunks)

        # Mock Claude
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Based on [Source 1], ocean freight costs $2500 per container.")]
        pipeline.client = AsyncMock()
        pipeline.client.messages.create = AsyncMock(return_value=mock_response)

        mock_db = AsyncMock()
        result = await pipeline.answer("What does ocean freight cost?", mock_db)

        assert "$2500" in result.answer
        assert len(result.chunks) == 1
        assert result.model_used == "claude-sonnet-4-20250514"
