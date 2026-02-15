"""Tests for the DocumentClassifier (Haiku-based classification)."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.document_extractor.classifier import DocumentClassifier
from app.schemas.extraction import DocumentType


@pytest.fixture
def mock_client():
    """Create a mock Anthropic client."""
    client = AsyncMock()
    return client


@pytest.fixture
def classifier(mock_client):
    return DocumentClassifier(client=mock_client, model="claude-haiku-4-5-20251001")


def _make_response(text: str):
    """Create a mock Claude API response."""
    mock_content = MagicMock()
    mock_content.text = text
    mock_response = MagicMock()
    mock_response.content = [mock_content]
    return mock_response


class TestClassification:
    async def test_classify_freight_invoice(self, classifier, mock_client):
        mock_client.messages.create.return_value = _make_response(
            '{"document_type": "freight_invoice"}'
        )
        result = await classifier.classify(text="FREIGHT INVOICE\nInvoice #: FI-2024-001")
        assert result == DocumentType.FREIGHT_INVOICE

    async def test_classify_bill_of_lading(self, classifier, mock_client):
        mock_client.messages.create.return_value = _make_response(
            '{"document_type": "bill_of_lading"}'
        )
        result = await classifier.classify(text="BILL OF LADING\nB/L Number: MAEU-123")
        assert result == DocumentType.BILL_OF_LADING

    async def test_classify_unknown(self, classifier, mock_client):
        mock_client.messages.create.return_value = _make_response(
            '{"document_type": "unknown"}'
        )
        result = await classifier.classify(text="Random document content")
        assert result == DocumentType.UNKNOWN

    async def test_handles_plain_text_response(self, classifier, mock_client):
        mock_client.messages.create.return_value = _make_response("freight_invoice")
        result = await classifier.classify(text="Some invoice text")
        assert result == DocumentType.FREIGHT_INVOICE

    async def test_handles_invalid_type(self, classifier, mock_client):
        mock_client.messages.create.return_value = _make_response(
            '{"document_type": "purchase_order"}'
        )
        result = await classifier.classify(text="Some PO text")
        assert result == DocumentType.UNKNOWN

    async def test_handles_api_error(self, classifier, mock_client):
        mock_client.messages.create.side_effect = Exception("API error")
        result = await classifier.classify(text="Some text")
        assert result == DocumentType.UNKNOWN

    async def test_empty_content_returns_unknown(self, classifier):
        result = await classifier.classify(text="", images=None)
        assert result == DocumentType.UNKNOWN

    async def test_uses_haiku_model(self, classifier, mock_client):
        mock_client.messages.create.return_value = _make_response(
            '{"document_type": "freight_invoice"}'
        )
        await classifier.classify(text="Invoice text")
        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "claude-haiku-4-5-20251001"
        assert call_kwargs["max_tokens"] == 100  # Small for classification

    async def test_truncates_long_text(self, classifier, mock_client):
        mock_client.messages.create.return_value = _make_response(
            '{"document_type": "freight_invoice"}'
        )
        long_text = "x" * 5000
        await classifier.classify(text=long_text)
        call_kwargs = mock_client.messages.create.call_args.kwargs
        message_content = call_kwargs["messages"][0]["content"]
        # The text content should be truncated to ~2000 chars + prefix
        text_block = next(c for c in message_content if c["type"] == "text")
        assert len(text_block["text"]) < 2200

    async def test_vision_input(self, classifier, mock_client):
        mock_client.messages.create.return_value = _make_response(
            '{"document_type": "bill_of_lading"}'
        )
        images = [{"base64": "dGVzdA==", "media_type": "image/png"}]
        result = await classifier.classify(images=images)
        assert result == DocumentType.BILL_OF_LADING
        # Verify image was included in the request
        call_kwargs = mock_client.messages.create.call_args.kwargs
        content = call_kwargs["messages"][0]["content"]
        assert any(c["type"] == "image" for c in content)
