"""Tests for the 2-pass extraction pipeline."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.document_extractor.pipeline import ExtractionPipeline, ExtractionResult
from app.schemas.extraction import DocumentType


MOCK_FREIGHT_EXTRACTION = {
    "invoice_number": "FI-2024-001",
    "invoice_date": "2024-12-01",
    "vendor_name": "Test Freight LLC",
    "shipper_name": None,
    "consignee_name": None,
    "origin": "Shanghai, China",
    "destination": "Los Angeles, CA",
    "currency": "USD",
    "line_items": [
        {"description": "Ocean Freight", "quantity": 1.0, "unit": "container", "unit_price": 2500.0, "total": 2500.0}
    ],
    "subtotal": 2500.0,
    "tax_amount": 0.0,
    "total_amount": 2500.0,
    "notes": None,
}

MOCK_BOL_EXTRACTION = {
    "bol_number": "MAEU-SH2024001",
    "issue_date": "2024-11-15",
    "carrier_name": "Maersk Line",
    "carrier_scac": "MAEU",
    "shipper": {"name": "Test Shipper", "address": "Shanghai, China"},
    "consignee": {"name": "Test Consignee", "address": "Newark, NJ"},
    "notify_party": None,
    "origin": {"city": "Shanghai", "state": None, "country": "China", "port": "CNSHA"},
    "destination": {"city": "Newark", "state": "NJ", "country": "USA", "port": "USNYC"},
    "vessel_name": "Test Vessel",
    "voyage_number": "001W",
    "container_numbers": ["MSKU1234567"],
    "cargo_description": "Electronics",
    "package_count": 100,
    "gross_weight": 5000.0,
    "weight_unit": "kg",
    "volume": 25.0,
    "volume_unit": "CBM",
    "freight_charges": 8000.0,
    "freight_payment_type": "prepaid",
    "special_instructions": None,
    "notes": None,
}


def _make_claude_response(data: dict) -> MagicMock:
    """Create a mock Claude API response."""
    mock_content = MagicMock()
    mock_content.text = json.dumps(data)
    mock_response = MagicMock()
    mock_response.content = [mock_content]
    return mock_response


@pytest.fixture
def csv_invoice(tmp_path) -> str:
    path = tmp_path / "test_invoice.csv"
    path.write_text(
        "FREIGHT INVOICE\n"
        "Invoice Number,FI-2024-001\n"
        "Vendor,Test Freight LLC\n"
        "Total,2500.00\n"
    )
    return str(path)


@pytest.fixture
def csv_bol(tmp_path) -> str:
    path = tmp_path / "test_bol.csv"
    path.write_text(
        "BILL OF LADING\n"
        "B/L Number,MAEU-SH2024001\n"
        "Carrier,Maersk Line\n"
    )
    return str(path)


@pytest.fixture
def mock_settings():
    from app.config import Settings
    return Settings(
        anthropic_api_key="test-key",
        claude_model="claude-sonnet-4-20250514",
        claude_haiku_model="claude-haiku-4-5-20251001",
        upload_dir="/tmp",
    )


class TestPipelineFlow:
    @patch("anthropic.AsyncAnthropic")
    async def test_full_pipeline_freight_invoice(self, MockAnthropic, csv_invoice, mock_settings):
        """Test the full pipeline: parse -> classify -> extract -> review."""
        mock_client = AsyncMock()
        MockAnthropic.return_value = mock_client

        # 3 calls: classify (Haiku), pass 1 (Sonnet), pass 2 (Sonnet)
        mock_client.messages.create.side_effect = [
            _make_claude_response({"document_type": "freight_invoice"}),
            _make_claude_response(MOCK_FREIGHT_EXTRACTION),
            _make_claude_response(MOCK_FREIGHT_EXTRACTION),
        ]

        pipeline = ExtractionPipeline(mock_settings)
        result = await pipeline.run(csv_invoice, "csv", "text/csv")

        assert isinstance(result, ExtractionResult)
        assert result.document_type == DocumentType.FREIGHT_INVOICE
        assert result.raw_extraction["invoice_number"] == "FI-2024-001"
        assert result.refined_extraction["total_amount"] == 2500.0
        assert result.processing_time_ms > 0
        assert mock_client.messages.create.call_count == 3

    @patch("anthropic.AsyncAnthropic")
    async def test_pipeline_with_forced_type(self, MockAnthropic, csv_invoice, mock_settings):
        """Test pipeline with forced document type (skips classification)."""
        mock_client = AsyncMock()
        MockAnthropic.return_value = mock_client

        # Only 2 calls (no classification)
        mock_client.messages.create.side_effect = [
            _make_claude_response(MOCK_FREIGHT_EXTRACTION),
            _make_claude_response(MOCK_FREIGHT_EXTRACTION),
        ]

        pipeline = ExtractionPipeline(mock_settings)
        result = await pipeline.run(
            csv_invoice, "csv", "text/csv",
            force_doc_type=DocumentType.FREIGHT_INVOICE,
        )

        assert result.document_type == DocumentType.FREIGHT_INVOICE
        assert mock_client.messages.create.call_count == 2

    @patch("anthropic.AsyncAnthropic")
    async def test_pipeline_bol_extraction(self, MockAnthropic, csv_bol, mock_settings):
        """Test pipeline with BOL document type."""
        mock_client = AsyncMock()
        MockAnthropic.return_value = mock_client

        mock_client.messages.create.side_effect = [
            _make_claude_response({"document_type": "bill_of_lading"}),
            _make_claude_response(MOCK_BOL_EXTRACTION),
            _make_claude_response(MOCK_BOL_EXTRACTION),
        ]

        pipeline = ExtractionPipeline(mock_settings)
        result = await pipeline.run(csv_bol, "csv", "text/csv")

        assert result.document_type == DocumentType.BILL_OF_LADING
        assert result.refined_extraction["bol_number"] == "MAEU-SH2024001"

    @patch("anthropic.AsyncAnthropic")
    async def test_pipeline_file_not_found(self, MockAnthropic, mock_settings):
        mock_client = AsyncMock()
        MockAnthropic.return_value = mock_client
        pipeline = ExtractionPipeline(mock_settings)
        with pytest.raises(FileNotFoundError):
            await pipeline.run("/nonexistent/file.csv", "csv", "text/csv")

    @patch("anthropic.AsyncAnthropic")
    async def test_pipeline_metadata(self, MockAnthropic, csv_invoice, mock_settings):
        """Test that pipeline returns useful metadata."""
        mock_client = AsyncMock()
        MockAnthropic.return_value = mock_client

        mock_client.messages.create.side_effect = [
            _make_claude_response({"document_type": "freight_invoice"}),
            _make_claude_response(MOCK_FREIGHT_EXTRACTION),
            _make_claude_response(MOCK_FREIGHT_EXTRACTION),
        ]

        pipeline = ExtractionPipeline(mock_settings)
        result = await pipeline.run(csv_invoice, "csv", "text/csv")

        assert result.metadata["page_count"] == 1
        assert result.metadata["vision_used"] is False
        assert result.metadata["text_chars"] > 0
        assert result.model_used == "claude-sonnet-4-20250514"
        assert result.haiku_model == "claude-haiku-4-5-20251001"
