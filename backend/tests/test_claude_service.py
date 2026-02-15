import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import Settings
from app.schemas.extraction import FreightInvoiceExtraction
from app.services.claude_service import ClaudeService


def make_mock_settings() -> Settings:
    return Settings(
        anthropic_api_key="test-key",
        claude_model="claude-sonnet-4-20250514",
        claude_max_tokens=4096,
        database_url="sqlite+aiosqlite:///test.db",
    )


SAMPLE_EXTRACTION = {
    "invoice_number": "INV-2026-001",
    "invoice_date": "2026-01-15",
    "vendor_name": "Acme Freight Corp",
    "shipper_name": "UPS Supply Chain",
    "consignee_name": "Warehouse Solutions LLC",
    "origin": "Atlanta, GA",
    "destination": "Chicago, IL",
    "currency": "USD",
    "line_items": [
        {
            "description": "FTL Transport - ATL to CHI",
            "quantity": 1,
            "unit": "load",
            "unit_price": 2500.00,
            "total": 2500.00,
        },
        {
            "description": "Fuel Surcharge",
            "quantity": 1,
            "unit": "flat",
            "unit_price": 375.00,
            "total": 375.00,
        },
    ],
    "subtotal": 2875.00,
    "tax_amount": 0,
    "total_amount": 2875.00,
    "notes": "Net 30 payment terms",
}


def make_mock_message(content_text: str):
    """Create a mock Anthropic message response."""
    mock_content = MagicMock()
    mock_content.text = content_text
    mock_message = MagicMock()
    mock_message.content = [mock_content]
    return mock_message


@pytest.mark.asyncio
async def test_extract_freight_invoice_parses_json():
    settings = make_mock_settings()
    service = ClaudeService(settings)

    mock_message = make_mock_message(json.dumps(SAMPLE_EXTRACTION))

    with patch.object(service.client.messages, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_message
        result = await service.extract_freight_invoice("Sample invoice text")

    assert isinstance(result, FreightInvoiceExtraction)
    assert result.invoice_number == "INV-2026-001"
    assert result.vendor_name == "Acme Freight Corp"
    assert result.total_amount == 2875.00
    assert len(result.line_items) == 2
    assert result.line_items[0].description == "FTL Transport - ATL to CHI"


@pytest.mark.asyncio
async def test_extract_freight_invoice_handles_markdown_wrapped_json():
    settings = make_mock_settings()
    service = ClaudeService(settings)

    wrapped = f"```json\n{json.dumps(SAMPLE_EXTRACTION)}\n```"
    mock_message = make_mock_message(wrapped)

    with patch.object(service.client.messages, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_message
        result = await service.extract_freight_invoice("Sample invoice text")

    assert result.invoice_number == "INV-2026-001"
    assert result.total_amount == 2875.00


@pytest.mark.asyncio
async def test_extract_freight_invoice_raises_on_invalid_json():
    settings = make_mock_settings()
    service = ClaudeService(settings)

    mock_message = make_mock_message("This is not JSON at all")

    with patch.object(service.client.messages, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_message

        with pytest.raises(ValueError, match="not valid JSON"):
            await service.extract_freight_invoice("Sample invoice text")


@pytest.mark.asyncio
async def test_extract_freight_invoice_sends_correct_model():
    settings = make_mock_settings()
    settings.claude_model = "claude-haiku-4-5-20251001"
    service = ClaudeService(settings)

    mock_message = make_mock_message(json.dumps(SAMPLE_EXTRACTION))

    with patch.object(service.client.messages, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_message
        await service.extract_freight_invoice("text")

    call_kwargs = mock_create.call_args.kwargs
    assert call_kwargs["model"] == "claude-haiku-4-5-20251001"


@pytest.mark.asyncio
async def test_extract_freight_invoice_handles_null_optional_fields():
    settings = make_mock_settings()
    service = ClaudeService(settings)

    minimal = {
        "invoice_number": "INV-001",
        "vendor_name": "Test Vendor",
        "total_amount": 100.0,
        "invoice_date": None,
        "shipper_name": None,
        "consignee_name": None,
        "origin": None,
        "destination": None,
        "currency": "USD",
        "line_items": [],
        "subtotal": None,
        "tax_amount": None,
        "notes": None,
    }
    mock_message = make_mock_message(json.dumps(minimal))

    with patch.object(service.client.messages, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_message
        result = await service.extract_freight_invoice("text")

    assert result.invoice_number == "INV-001"
    assert result.shipper_name is None
    assert result.line_items == []
